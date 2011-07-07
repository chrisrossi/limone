======
Limone
======

Limone is a library for generating content types from a Colander_ schema. A
content type is, in this context, a class that implements the structure and
constraints specified by the schema. This allows a developer to easily
generate model objects which enforce the constraints of the schema, performing
validation during initialization and attribute assignment. Objects are
serializable and deserializable via Colander's serialization.  Because types
are generated at runtime, Limone also suggests the development of applications
where the structure of the objects used to store your application's data can
be derived from configuration or user input.

.. _Colander: http://docs.pylonsproject.org/projects/colander/dev/


Creating Content Types Declaratively
------------------------------------

Content types can be generated declaratively from schema definitions using
decorators. Let's take a look at the following Colander schema as an example,
taken from the Colander documentation::

    import colander

    class Friend(colander.TupleSchema):
        rank = colander.SchemaNode(colander.Int(),
                                  validator=colander.Range(0, 9999))
        name = colander.SchemaNode(colander.String())

    class Phone(colander.MappingSchema):
        location = colander.SchemaNode(colander.String(),
                                      validator=colander.OneOf(['home', 'work']))
        number = colander.SchemaNode(colander.String())

    class Friends(colander.SequenceSchema):
        friend = Friend()

    class Phones(colander.SequenceSchema):
        phone = Phone()

    class Person(colander.MappingSchema):
        name = colander.SchemaNode(colander.String())
        age = colander.SchemaNode(colander.Int(),
                                 validator=colander.Range(0, 200))
        friends = Friends()
        phones = Phones()

The simplest way to generate a `Person` content type is to add the
`limone.content_schema` decorator::

    import colander
    import limone

    ... <elided for brevity>

    @limone.content_schema
    class Person(colander.MappingSchema):
        name = etc...

Instances of Person can then be created in the usual way::

    jack = Person(
        name='Jack',
        age=52,
        friends=[
            (1, 'Fred'),
            (2, 'Barney')
        ],
        phones=[
            {'location': 'home',
             'number': '555-1212'},
        ])

Assigning a value to an attribute triggers Colander schema validation.  For
example, when a value of `300` is assigned to `age`::

    jack.age = 300

A `colander.Invalid` exception is raised::

    colander.Invalid: {'age': u'300 is greater than maximum value 200'}

When instantiating a content type, values for all required attributes must be
provided::

    fred = Person()

Raises::

    colander.Invalid: {'age': u'Required', 'name': u'Required'}


Decorating a Class With a Schema
--------------------------------

In some cases you might want to define a class separately from its schema. For
this you can use the `limone.content_type` decorator. Let's say that instead
of turning the `Person` schema into a content type directly, we have an
`HRPerson` class which extends a hypothetical `HRRecord` class that we want to
use for our content type::

    @limone.content_type(Person)
    class HRPerson(HRRecord):
        pass

    fred = HRPerson(name='Fred', age=54)

**NOTE** The decorated class must have a no-arg constructor.


Creating a Content Type Imperatively
------------------------------------

The above examples use a declarative style for creating content types. Using
the `make_content_type` function, we can also generate new content types
imperatively. Assuming `HRPerson` has been defined as a class, the example
above could have been written::

    content_type = limone.make_content_type(Person, 'Person', bases=(HRPerson,))
    fred = content_type(name='Joe', age=54)

The full signature for the `make_content_type` function is::

    make_content_type(schema, name, module=None, bases=(object,))

+ `schema` is the Colander schema to use to generate the class.

+ The value of the `name` parameter will be assigned to the `__name__`
  attribute of the generated class. If added to a registry, the name will also
  be used as the key for looking up the content type later. (See `Using the
  Limone Registry`_.)

+ `module`, if specified, will be used to set the `__module__` attribute of
  the generated class.

+ `bases` can be specified as a tuple of types that are the superclasses for
  the generated classes.  **NOTE** The first base class must have a no-arg
  constructor.


Using the Limone Registry
-------------------------

Instances `limone.Registry` can be used to keep track of available content
types.  An instance of `limone.Registry` is required to make content types
available via an import hook.  (See `Using the Import Hook`_.)  Content types
are added to the registry using the `register_content_type` method::

    registry = limone.Registry()
    registry.regsister_content_type(Person)

The `get_content_type` method is used to retrieve a content type by name::

    content_type = registry.get_content_type('Person')
    joe = content_type(name='Joe', age=54)

A tuple of all of the registered content types can be retrieved using the
`get_content_types` method::

    for content_type in registry.get_content_types():
        print content_type.__name__, content_type

Prints::

    Person <class 'Person'>


Using the Import Hook
---------------------

In the above two declarative examples, because types were being generated at
module scope, they can be imported using the standard Python import mechanism.
For content types that are generated imperatively, however, there may not be a
global name that can be used to import the type.  This would definitely be the
case in an application that generated content types from schemas that were
generated at runtime through configuration or user input.  This can lead to
difficulties--pickling, for example, does not work if the class can't be found
by Python's import mechanism.  Using the imperative example from earlier, let's
see what happens when we try to pickle and then unpickle an instance of the
`Person` content type::

    import pickle

    content_type = make_content_type(PersonSchema, 'Person', bases=(HRPerson,))
    fred = content_type(name='Fred', age=54)
    fred2 = pickle.loads(pickle.dumps(fred))
    assert fred is not fred2
    assert fred.serialize() == fred2.serialize()

We get this exception::

    pickle.PicklingError: Can't pickle <class 'Person'>: it's not found as __main__.Person

What we can do, though, is hook Python's import mechanism so that Python can
look up the content type in our Limone instance.  This requires that the
content type be registered with an instance of `limone.Registry`::

    import pickle

    registry = limone.Registry()
    registry.register_content_type(Person)
    registry.hook_import()

    content_type = make_content_type(PersonSchema, 'Person', bases=(HRPerson,))
    fred = content_type(name='Fred', age=54)
    fred2 = pickle.loads(pickle.dumps(fred))
    assert fred is not fred2
    assert fred.serialize() == fred2.serialize()

    registry.unhook_import()

The pickle and unpickle operations are now successful because pickle is able
to look up the type using Python's import mechanism.

The signature for `hook_import` is::

    hook_import(module='__limone__')

The `hook_import` method inserts an object into `sys.meta_path` that can look
up content types in the registry. The `module` parameter is used to set the
`__module__` attribute on generated content types. This will also be used by
the import hook to identify the types that it is able to import. Using the
default value for `module`, with the import hook in place, we see that we can
import imperatively generated content types in the standard Pythonic way::

    from __limone__ import Person
    fred = Person(name='Fred', age=54)

The default value for `module` should not be used if you expect that an
application will use more than one `limone.Registry` instance inside of a
single process. In this case, a different value of `module` should be used for
each instance so that each instance only tries to find its own content types.

The `unhook_import` method cleans up a previously made import hook, returning
`sys.meta_path` to its previous state.


Using Colander`s Serialization/Deserialization
----------------------------------------------

Instances of a content type can be serialized using Colander's serialization::

    jack = Person(
        name='Jack',
        age=52,
        friends=[
            (1, 'Fred'),
            (2, 'Barney')
        ],
        phones=[
            {'location': 'home',
             'number': '555-1212'},
        ])

    from pprint import pprint
    pprint(jack.serialize())

Produces this output::

    {'age': '52',
     'friends': [('1', u'Fred'), ('2', u'Barney')],
     'name': u'Jack',
     'phones': [{'location': u'home', 'number': u'555-1212'}]}

Note that Colander's serialization is a kind of intermediate format.  All
scalar values are serialized to strings, but sequences, tuples and mappings
are returned as lists, tuples and dicts, respectively.  This intermediate form
is easily fed into other serializers, like json, to produce a serialized
byte sequence.

Instances can be instantiated via Colander's deserialization::

    jack = Person.deserialize(
        {'age': '52',
         'friends': [('1', u'Fred'), ('2', u'Barney')],
         'name': u'Jack',
         'phones': [{'location': u'home', 'number': u'555-1212'}]})

Deserialization can also be used to update an existing instance::

    jack.deserialize_update({'age': '53'})

