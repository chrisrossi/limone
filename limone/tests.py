import unittest2


class MakeContentTypeTests(unittest2.TestCase):

    def test_schema_is_wrong_type(self):
        import limone
        with self.assertRaises(TypeError):
            limone.Limone().add_content_type('Foo', object)


class ShallowSchemaTests(unittest2.TestCase):

    def setUp(self):
        import colander
        from limone import Limone

        self.limone = limone = Limone()
        limone.hook_import()

        class PersonSchema(colander.Schema):
            name = colander.SchemaNode(colander.String('UTF-8'))
            age = colander.SchemaNode(colander.Integer())

        self.schema = PersonSchema

        @limone.content_type(PersonSchema)
        class Person(object):
            pass

        self.content_type = Person

    def tearDown(self):
        self.limone.unhook_import()

    def test_content_type(self):
        ct = self.content_type
        self.assertEqual(ct.__bases__[0].__name__, 'Person')
        self.assertEqual(ct.__name__, 'Person')

    def test_hook_import(self):
        import limone
        import sys

        __import__('__limone__')
        module = sys.modules['__limone__']
        self.assertIsInstance(module, limone.Limone)
        self.assertEqual(module.Person, self.content_type)

    def test_constructor(self):
        joe = self.content_type(name='Joe', age=35)
        self.assertEqual(joe.name, 'Joe')
        self.assertEqual(joe.age, 35)

    def test_getset(self):
        joe = self.content_type(name='Joe', age=35)
        joe.name = 'Chris'
        joe.age = 40
        self.assertEqual(joe.name, 'Chris')
        self.assertEqual(joe.age, 40)

    def test_missing_fields(self):
        import colander
        with self.assertRaises(colander.Invalid) as ecm:
            joe = self.content_type()

        self.assertEqual(ecm.exception.asdict(), {
            'name.age': u'Required', 'name.name': u'Required'})

    def test_missing_fields_w_defaults(self):
        self.schema = schema = self.schema()
        schema['name'].default = 'Paul'
        schema['age'].default = 200
        paul = self.content_type()
        self.assertEqual(paul.name, 'Paul')
        self.assertEqual(paul.age, 200)

    def test_validation_on_assignment(self):
        import colander
        joe = self.content_type(name='Joe', age=35)
        with self.assertRaises(colander.Invalid):
            joe.name = 1234
        with self.assertRaises(colander.Invalid):
            joe.age = 'thirty five'

    def test_extra_kw_args(self):
        with self.assertRaises(TypeError):
            self.content_type(name='Joe', age=35, sex='male')

    def test_serialize(self):
        joe = self.content_type(name='Joe', age=35)
        self.assertEqual(joe.serialize(), {'age': '35', 'name': 'Joe'})

    def test_deserialize(self):
        joe = self.content_type.deserialize({'age': '35', 'name': 'Joe'})
        self.assertEqual(joe.name, 'Joe')
        self.assertEqual(joe.age, 35)

    def test_deserialize_update(self):
        joe = self.content_type(name='Joe', age=35)
        joe.deserialize_update({'age': '40', 'name': 'Gio'})
        self.assertEqual(joe.name, 'Gio')
        self.assertEqual(joe.age, 40)

    def test_can_pickle(self):
        import pickle
        joe = self.content_type(name='Joe', age=35)
        new_joe = pickle.loads(pickle.dumps(joe))
        self.assertEqual(new_joe.name, 'Joe')
        self.assertEqual(new_joe.age, 35)
        self.assertIsInstance(new_joe, self.content_type)


import colander
from limone import Limone as Limone
limone = Limone()

@limone.content_schema
class Cat(colander.Schema):
    fur = colander.SchemaNode(colander.String('UTF-8'))

class TestTypesAtModuleScopeDontNeedImportHooks(unittest2.TestCase):

    def test_can_pickle(self):
        import pickle
        lily = Cat(fur='tabby')
        print 'debug', Cat.__module__
        lily = pickle.loads(pickle.dumps(lily))
        self.assertEqual(lily.fur, 'tabby')
