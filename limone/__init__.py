import colander


def content_type(schema):
    """
    Decorator for turning a class into a content type using the passed in
    Colander schema.
    """
    def decorator(cls):
        return make_content_type(schema, cls, cls.__name__)
    return decorator


def make_content_type(schema, base=object, name=None):
    """
    Generate a content type class from a Colander schema.
    """
    if isinstance(schema, type):
        schema = schema()

    if type(getattr(schema, 'typ', None)) != colander.Mapping:
        raise TypeError('Schema must be a colander mapping schema.')

    schema = schema.clone() # protect us from outside mutation
    content_type = _content_type_factory(schema, base, name)

    return content_type


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


def _content_type_factory(node, base=object, name=None):

    class ContentType(base):
        _schema_node = node

        @classmethod
        def deserialize(cls, cstruct):
            appstruct = cls._schema_node.deserialize(cstruct)
            return cls(**appstruct)

        def __init__(self, **kw):
            kw = self._update_from_dict(kw, skip_missing=False)

            if kw:
                raise TypeError(
                    "Unexpected keyword argument(s): %s" % repr(kw))

        def deserialize_update(self, cstruct):
            error = None
            schema = self._schema_node
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

        def _update_from_dict(self, data, skip_missing):
            error = None

            for i, node in enumerate(self._schema_node.children):
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
            for child in self._schema_node.children:
                name = child.name
                data[name] = _appstruct_node(child, getattr(self, name))
            return data

        def serialize(self):
            return self._schema_node.serialize(self._appstruct())

    if name is not None:
        ContentType.__name__ = name

    for child in node.children:
        setattr(ContentType, child.name, _make_property(child))

    return ContentType


def _appstruct_node(node, value):
    return value
