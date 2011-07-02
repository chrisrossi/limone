import colander
import sys

default = object()


class Limone(object):
    module = None
    _finder_loader = None

    def __init__(self):
        self._types = {}

    def content_type(self, schema):
        """
        Decorator for turning a class into a content type using the passed in
        Colander schema.
        """
        def decorator(cls):
            module = self.module
            if module is None:
                module = cls.__module__
            return self.add_content_type(cls.__name__, schema, module, (cls,))
        return decorator

    def content_schema(self, schema):
        """
        Decorator for turning a Colander schema into a content type.
        """
        module = self.module
        if module is None:
            module = schema.__module__
        return self.add_content_type(schema.__name__, schema, module)

    def add_content_type(self, name, schema, module=None, bases=(object,)):
        """
        Generate a content type class from a Colander schema.
        """
        if module is None:
            module = self.module
        content_type = _content_type_factory(module, name, schema, bases)
        self._types[name] = content_type
        return content_type

    def get_content_type(self, name):
        return self._types.get(name)

    __getattr__ = get_content_type

    def hook_import(self, module='__limone__'):
        self._finder_loader =  _FinderLoader(self, module)
        self.module = module

    def unhook_import(self):
        self._finder_loader.unload()
        del self.module
        del self._finder_loader


class _LeafNodeProperty(object):

    def __init__(self, node):
        self.node = node
        name = node.name
        assert name
        self._attr = '.' + name

    def __get__(self, obj, cls):
        return obj.__dict__[self._attr]

    def __set__(self, obj, value):
        value = self._validate(value)
        obj.__dict__[self._attr] = value

    def _validate(self, value):
        # serialize/deserialize forces colander to validate
        # also will replace null values with defaults
        node = self.node
        return node.deserialize(node.serialize(value))


def _make_property(node):
    return _LeafNodeProperty(node)


def _appstruct_node(node, value):
    return value


def _content_type_factory(module, name, schema, bases):
    """
    Generate a content type class from a Colander schema.
    """
    if isinstance(schema, type):
        schema = schema()

    if type(getattr(schema, 'typ', None)) != colander.Mapping:
        raise TypeError('Schema must be a colander mapping schema.')

    class MetaType(type):
        def __new__(cls, throw, away, members):
            return type.__new__(cls, name, bases, members)

        def __init__(cls, throw, away, members):
            type.__init__(cls, name, bases, members)
            cls.__module__ = module

    class ContentType(object):
        __metaclass__ = MetaType
        __schema__ = schema

        @classmethod
        def deserialize(cls, cstruct):
            appstruct = cls.__schema__.deserialize(cstruct)
            return cls(**appstruct)

        def __init__(self, **kw):
            kw = self._update_from_dict(kw, skip_missing=False)

            if kw:
                raise TypeError(
                    "Unexpected keyword argument(s): %s" % repr(kw))

        def deserialize_update(self, cstruct):
            error = None
            schema = self.__schema__
            appstruct = {}
            for i, (name, value) in enumerate(cstruct.items()):
                node = schema[name]
                try:
                    appstruct[name] = node.deserialize(value)
                except colander.Invalid, e:
                    if error is None:
                        error = colander.Invalid(schema)
                    error.add(e, i)

            self._update_from_dict(appstruct, skip_missing=True)

        def serialize(self):
            return self.__schema__.serialize(self._appstruct())

        def _update_from_dict(self, data, skip_missing):
            error = None

            for i, node in enumerate(self.__schema__.children):
                name = node.name
                try:
                    setattr(self, name, data.pop(name, colander.null))
                except colander.Invalid, e:
                    if error is None:
                        error = colander.Invalid(node)
                    error.add(e, i)

            if error is not None:
                raise error

            return data

        def _appstruct(self):
            data = {}
            for child in self.__schema__.children:
                name = child.name
                data[name] = _appstruct_node(child, getattr(self, name))
            return data

    for child in schema.children:
        setattr(ContentType, child.name, _make_property(child))

    return ContentType


class _FinderLoader(object):
    def __init__(self, limone, module):
        self.limone = limone
        self.module = module
        sys.meta_path.append(self)

    def find_module(self, module, package_path):
        if module == self.module:
            return self

    def load_module(self, module):
        limone = self.limone
        sys.modules[module] = self
        return limone

    def __getattr__(self, name):
        return self.limone.get_content_type(name)

    def unload(self):
        sys.meta_path.remove(self)
        module = self.module
        if module in sys.modules:
            del sys.modules[module]
        del self.limone
