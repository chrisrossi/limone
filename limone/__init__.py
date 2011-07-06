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

    def hook_import(self, module='__limone__'):
        self._finder_loader =  _FinderLoader(self, module)
        self.module = module

    def unhook_import(self):
        self._finder_loader.unload()
        del self.module
        del self._finder_loader


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

            if error is not None:
                raise error

            self._update_from_dict(appstruct, skip_missing=True)

        def serialize(self):
            return self.__schema__.serialize(self._appstruct())

        def _update_from_dict(self, data, skip_missing):
            error = None
            schema = self.__schema__

            for i, node in enumerate(schema.children):
                name = node.name
                try:
                    setattr(self, name, data.pop(name, colander.null))
                except colander.Invalid, e:
                    if error is None:
                        error = colander.Invalid(schema)
                    error.add(e, i)

            if error is not None:
                raise error

            return data

        def _appstruct(self):
            return [(node.name, _appstruct_node(getattr(self, node.name)))
                    for node in self.__schema__]

    for node in schema:
        setattr(ContentType, node.name, _make_property(node))

    return ContentType


class _LeafNodeProperty(object):

    def __init__(self, node):
        self.node = node
        name = node.name
        assert name
        self._attr = '.' + name

    def __get__(self, obj, cls=None):
        return obj.__dict__[self._attr]

    def __set__(self, obj, value):
        value = self._validate(value)
        obj.__dict__[self._attr] = value
        return value

    def _validate(self, value):
        # serialize/deserialize forces colander to validate
        # also will replace null values with defaults
        node = self.node
        return node.deserialize(node.serialize(value))


class _MappingNodeProperty(_LeafNodeProperty):

    def _validate(self, value):
        if value is colander.null:
            value = {}
        return _MappingNode(self.node, value)


class _MappingNode(object):

    def __init__(self, schema, appstruct):
        schema.typ._validate(schema, appstruct) # XXX private colander api
        props = {}
        error = None
        data = appstruct.copy()
        for i, node in enumerate(schema):
            name = node.name
            props[name] = prop = _make_property(node)
            try:
                prop.__set__(self, data.pop(name, colander.null))
            except colander.Invalid, e:
                if error is None:
                    error = colander.Invalid(schema)
                error.add(e, i)

        if error is not None:
            raise error

        if data:
            raise TypeError(
                "Unexpected keyword argument(s): %s" % repr(data))

        self.__dict__['__schema__'] = schema
        self.__dict__['_props'] = props

    def __getattr__(self, name):
        prop = self._props.get(name, None)
        if prop is None:
            raise AttributeError(name)
        return prop.__get__(self)

    def __setattr__(self, name, value):
        prop = self._props.get(name, None)
        if prop is None:
            return super(_MappingNode, self).__setattr__(name, value)
        return prop.__set__(self, value)

    def _appstruct(self):
        return [(name, _appstruct_node(prop.__get__(self))) for
                name, prop in self._props.items()]


class _SequenceNodeProperty(_LeafNodeProperty):

    def _validate(self, value):
        if value is colander.null:
            value = []
        return _SequenceNode(self.node, value)


class _SequenceNode(object):

    def __init__(self, schema, appstruct):
        # XXX calls private colander api.
        schema.typ._validate(schema, appstruct, schema.typ.accept_scalar)
        self.__schema__ = schema
        self._prop = prop = _make_property(schema.children[0])

        data = []
        error = None
        for i, item in enumerate(appstruct):
            try:
                data.append(_SequenceItem(prop, item))
            except colander.Invalid, e:
                if error is None:
                    error = colander.Invalid(schema)
                error.add(e, i)

        if error is not None:
            raise error

        self._data = data

    def __getitem__(self, index):
        return self._data[index].get()

    def __setitem__(self, index, value):
        return self._data[index].set(value)

    def __delitem__(self, index):
        del self._data[index]

    def __iter__(self):
        for item in self._data:
            yield item.get()

    def __cmp__(self, right):
        return cmp(list(self), right)

    def __repr__(self):
        return repr(list(self))

    def append(self, item):
        self._data.append(_SequenceItem(self._prop, item))

    def extend(self, items):
        prop = self._prop
        data = self._data
        for item in items:
            data.append(_SequenceItem(prop, item))

    def count(self, item):
        n = 0
        for x in self:
            if x == item:
                n += 1
        return n

    def index(self, item, start=0, stop=None):
        if stop is None:
            stop = len(self)
        data = self._data
        for index in xrange(start, stop):
            x = data[index].get()
            if x == item:
                return index
        raise ValueError("'%s' not in list" % item)

    def __len__(self):
        return len(self._data)

    def insert(self, index, item):
        self._data.insert(index, _SequenceItem(self._prop, item))

    def pop(self, index=-1):
        return self._data.pop(index).get()

    def remove(self, item):
        del self[self.index(item)]

    def reverse(self):
        self._data.reverse()

    def __getslice__(self, i, j):
        return [item.get() for item in self._data[i:j]]

    def __setslice__(self, i, j, s):
        error = None
        items = []
        prop = self._prop
        for index, item in enumerate(s):
            try:
                items.append(_SequenceItem(prop, item))
            except colander.Invalid, e:
                if error is None:
                    error = colander.Invalid(self.__schema__)
                error.add(e, i + index)

        if error is not None:
            raise error

        self._data[i:j] = items

    def __delslice__(self, i, j):
        del self._data[i:j]


class _SequenceItem(object):

    def __init__(self, prop, value):
        self._prop = prop
        prop.__set__(self, value)

    def get(self):
        return self._prop.__get__(self)

    def set(self, value):
        return self._prop.__set__(self, value)


class _TupleNodeProperty(_LeafNodeProperty):

    def __init__(self, node):
        super(_TupleNodeProperty, self).__init__(node)
        self._props = tuple(_make_property(child) for child in node)

    def _validate(self, value):
        node = self.node
        node.typ._validate(node, value) # XXX private colander api
        items = []
        error = None
        for i, (item, prop) in enumerate(zip(value, self._props)):
            try:
                items.append(_SequenceItem(prop, item))
            except colander.Invalid, e:
                if error is None:
                    error = colander.Invalid(node)
                error.add(e, i)

        if error is not None:
            raise error

        return tuple(item.get() for item in items)


def _make_property(node):
    type = node.typ
    if isinstance(type, colander.Mapping):
        return _MappingNodeProperty(node)
    if isinstance(type, colander.Sequence):
        return _SequenceNodeProperty(node)
    if isinstance(type, colander.Tuple):
        return _TupleNodeProperty(node)
    return _LeafNodeProperty(node)


def _appstruct_node(value):
    get_appstruct = getattr(value, '_appstruct', None)
    if get_appstruct is not None:
        return get_appstruct()
    return value


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
