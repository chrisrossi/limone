import colander
import sys
import venusian


class Registry(object):
    """
    Content type registry.
    """
    _finder_loader = None

    def __init__(self):
        self._types = {}

    def register_content_type(self, content_type):
        """
        Generate a content type class from a Colander schema.
        """
        self._types[content_type.__name__] = content_type
        if self._finder_loader is not None:
            content_type._original__module__ = content_type.__module__
            content_type.__module__ = self._finder_loader.module

    def get_content_type(self, name):
        """
        Retrieve a content type by name.
        """
        return self._types.get(name)

    def get_content_types(self):
        """
        Retrieve a tuple containing all of the content types registered with
        this instance.
        """
        return tuple(self._types.values())

    def hook_import(self, module='__limone__'):
        """
        Hook into the Python import mechanism so that registered content types
        can be registered
        """
        self._finder_loader =  _FinderLoader(self, module)
        for ct in self._types.values():
            ct._original__module__ = ct.__module__
            ct.__module__ = module

    def unhook_import(self):
        """
        Undo the import hook.
        """
        if self._finder_loader is not None:
            self._finder_loader.unload()
            del self._finder_loader
            for ct in self._types.values():
                ct.__module__ = ct._original__module__
                del ct._original__module__

    def scan(self, module):
        scanner = venusian.Scanner(limone=self)
        scanner.scan(module, categories=('limone',))


class _ContentSchemaDecorator(object):
    """
    Decorator for turning a Colander schema into a content type.
    """
    def __init__(self, meta=type, property_factory=None):
        self.meta = meta
        self.property_factory = property_factory

    def __call__(self, schema):
        ct = make_content_type(
            schema, schema.__name__, schema.__module__, meta=self.meta,
            property_factory=self.property_factory
        )
        def callback(scanner, name, ob):
            scanner.limone.register_content_type(ct)
        venusian.attach(ct, callback, category='limone')
        return ct


content_schema = _ContentSchemaDecorator()


class _ContentTypeDecorator(object):
    """
    Decorator for turning a class into a content type using the passed in
    Colander schema.
    """
    def __init__(self, meta=type, property_factory=None):
        self.meta = meta
        self.property_factory = property_factory

    def __call__(self, schema):
        def decorator(cls):
            ct = make_content_type(
                schema, cls.__name__, cls.__module__, (cls,), self.meta,
                property_factory=self.property_factory
            )
            def callback(scanner, name, ob):
                scanner.limone.register_content_type(ct)
            venusian.attach(ct, callback, category='limone')
            return ct
        return decorator


content_type = _ContentTypeDecorator()


def make_content_type(schema, name, module=None, bases=(object,), meta=type,
                      property_factory=None):
    """
    Generate a content type class from a Colander schema.
    """
    if isinstance(schema, type):
        schema = schema()

    if type(getattr(schema, 'typ', None)) != colander.Mapping:
        raise TypeError('Schema must be a colander mapping schema.')

    if property_factory is None:
        property_factory = PropertyFactory()

    class MetaType(meta):
        def __new__(cls, throw, away, members):
            return meta.__new__(cls, name, bases, members)

        def __init__(cls, throw, away, members):
            meta.__init__(cls, name, bases, members)
            cls.__module__ = module
            cls.__content_type__ = cls

    class ContentType(object):
        __metaclass__ = MetaType
        __schema__ = schema
        _property_factory = property_factory
        _MappingNode = _MappingNode
        _SequenceNode = _SequenceNode
        _SequenceItem = _SequenceItem

        @classmethod
        def deserialize(cls, cstruct):
            appstruct = cls.__schema__.deserialize(cstruct)
            return cls(**appstruct)

        def __init__(self, **kw):
            try:
                super(ContentType, self).__init__()
            except TypeError:
                # Substitute error message more pertinent to situation at hand.
                raise TypeError(
                    'Limone content types may only extend types with no-arg '
                    'constructors.')

            self.__content__ = self
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
                    value = data.pop(name, colander.null)
                    if value is colander.null and skip_missing:
                        continue
                    setattr(self, name, value)
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

    property_factory = ContentType._property_factory
    for node in schema:
        setattr(ContentType, node.name, property_factory(ContentType, node))

    return ContentType


class _LeafNodeProperty(object):

    def __init__(self, content, node):
        self.content = content
        self.node = node
        name = node.name
        assert name
        self._attr = '.' + name

    def __get__(self, obj, cls=None):
        return obj.__dict__[self._attr]

    def __set__(self, obj, value):
        value = self._validate(obj.__content__, value)
        setattr(obj, self._attr, value)
        return value

    def _validate(self, content, value):
        # serialize/deserialize forces colander to validate
        # also will replace null values with defaults
        node = self.node
        return node.deserialize(node.serialize(value))


class _MappingNodeProperty(_LeafNodeProperty):

    def _validate(self, content, value):
        if value is colander.null:
            value = {}
        return content._MappingNode(content, self.node, value)


class _MappingNode(object):

    def __init__(self, content, schema, appstruct):
        self.__dict__['__content__'] = content
        schema.typ._validate(schema, appstruct) # XXX private colander api
        props = {}
        error = None
        data = appstruct.copy()
        property_factory = content._property_factory
        for i, node in enumerate(schema):
            name = node.name
            props[name] = prop = property_factory(content, node)
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
        props = self.__dict__.get('_props')
        if props is not None:
            prop = props.get(name)
            if prop is not None:
                return prop.__set__(self, value)
        return super(_MappingNode, self).__setattr__(name, value)

    def _appstruct(self):
        return [(name, _appstruct_node(prop.__get__(self))) for
                name, prop in self._props.items()]


class _SequenceNodeProperty(_LeafNodeProperty):

    def _validate(self, content, value):
        if value is colander.null:
            value = []
        return content._SequenceNode(content, self.node, value)


class _SequenceNode(object):
    _data_type = list

    def __init__(self, content, schema, appstruct):
        # XXX calls private colander api.
        self.__content__ = content
        schema.typ._validate(schema, appstruct, schema.typ.accept_scalar)
        self.__schema__ = schema
        property_factory = content._property_factory
        self._prop = prop = property_factory(content, schema.children[0])

        data = self._data_type()
        error = None
        for i, item in enumerate(appstruct):
            try:
                data.append(content._SequenceItem(content, prop, item))
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
        content = self.__content__
        self._data[index] = content._SequenceItem(content, self._prop, value)

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
        content = self.__content__
        self._data.append(
            content._SequenceItem(content, self._prop, item))

    def extend(self, items):
        prop = self._prop
        data = self._data
        content = self.__content__
        for item in items:
            data.append(content._SequenceItem(content, prop, item))

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
        content = self.__content__
        self._data.insert(index, content._SequenceItem(
            content, self._prop, item))

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
        content = self.__content__
        for index, item in enumerate(s):
            try:
                items.append(
                    content._SequenceItem(content, prop, item))
            except colander.Invalid, e:
                if error is None:
                    error = colander.Invalid(self.__schema__)
                error.add(e, i + index)

        if error is not None:
            raise error

        self._data[i:j] = items

    def __delslice__(self, i, j):
        del self._data[i:j]

    def _appstruct(self):
        return [_appstruct_node(item) for item in self]


class _SequenceItem(object):

    def __init__(self, content, prop, value):
        self.__content__ = content
        self._prop = prop
        prop.__set__(self, value)

    def get(self):
        return self._prop.__get__(self)


class _TupleNodeProperty(_LeafNodeProperty):

    def __init__(self, content, node):
        super(_TupleNodeProperty, self).__init__(content, node)
        property_factory = content._property_factory
        self._props = tuple(property_factory(content, child) for child in node)

    def _validate(self, content, value):
        node = self.node
        node.typ._validate(node, value) # XXX private colander api
        items = []
        error = None
        for i, (item, prop) in enumerate(zip(value, self._props)):
            try:
                items.append(
                    content._SequenceItem(content, prop, item))
            except colander.Invalid, e:
                if error is None:
                    error = colander.Invalid(node)
                error.add(e, i)

        if error is not None:
            raise error

        return tuple(item.get() for item in items)


class PropertyFactory(object):

    def __init__(self):
        self.registry = {
            colander.Mapping: _MappingNodeProperty,
            colander.Sequence: _SequenceNodeProperty,
            colander.Tuple: _TupleNodeProperty,
            colander.SchemaType: _LeafNodeProperty,
        }

    def __call__(self, content, node):
        registry = self.registry
        for cls in type(node.typ).mro():
            prop_cls = registry.get(cls)
            if prop_cls is not None:
                return prop_cls(content, node)


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
        return self

    def __getattr__(self, name):
        return self.limone.get_content_type(name)

    def unload(self):
        sys.meta_path.remove(self)
        module = self.module
        if module in sys.modules:
            del sys.modules[module]
        del self.limone
