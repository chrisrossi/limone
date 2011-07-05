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
        self.assertIsInstance(module.limone, limone.Limone)
        self.assertEqual(module.Person, self.content_type)

    def test_constructor(self):
        joe = self.content_type(name='Joe', age=35)
        self.assertEqual(joe.name, 'Joe')
        self.assertEqual(joe.age, 35)

    def test_constructor_invalid(self):
        import colander
        with self.assertRaises(colander.Invalid) as ecm:
            joe = self.content_type(age='thirty five')
        self.assertEqual(ecm.exception.asdict(), {
            'age': u'"thirty five" is not a number', 'name': u'Required'})

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
            'age': u'Required', 'name': u'Required'})

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

    def test_deserialize_update_invalid(self):
        import colander
        joe = self.content_type(name='Joe', age=35)
        with self.assertRaises(colander.Invalid) as ecm:
            joe.deserialize_update({'age': 'forty', 'name': None})
        self.assertEqual(ecm.exception.asdict(), {
            'age': u'"forty" is not a number', 'name': u'Required'})

    def test_can_pickle_instance(self):
        import pickle
        joe = self.content_type(name='Joe', age=35)
        new_joe = pickle.loads(pickle.dumps(joe))
        self.assertEqual(new_joe.name, 'Joe')
        self.assertEqual(new_joe.age, 35)
        self.assertIsInstance(new_joe, self.content_type)

    def test_can_pickle_type(self):
        import pickle
        ct = pickle.loads(pickle.dumps(self.content_type))
        self.assertEqual(ct.__schema__.children[0].name, 'name')


class NestedMappingNodeTests(unittest2.TestCase):

    def setUp(self):
        import colander
        from limone import Limone

        limone = Limone()

        class NSAData(colander.Schema):
            serialnum = colander.SchemaNode(colander.Str('UTF-8'))
            date_of_contact = colander.SchemaNode(colander.Date())

        class PersonalData(colander.Schema):
            nsa_data = NSAData()
            n_arrests = colander.SchemaNode(colander.Int())

        class PersonSchema(colander.Schema):
            name = colander.SchemaNode(colander.Str('UTF-8'))
            age = colander.SchemaNode(colander.Integer(), default=500)
            personal = PersonalData()

        self.content_type = limone.add_content_type('Person', PersonSchema)

    def test_construction(self):
        import datetime
        day = datetime.date(2010, 5, 12)
        jack = self.content_type(**{
            'name': 'Jack',
            'age': 500,
            'personal': {
                'nsa_data': {
                    'serialnum': 'abc123',
                    'date_of_contact': day,
                },
                'n_arrests': 5,
            },
        })
        self.assertEqual(jack.name, 'Jack')
        self.assertEqual(jack.age, 500)
        self.assertEqual(jack.personal.nsa_data.serialnum, 'abc123')
        self.assertEqual(jack.personal.nsa_data.date_of_contact, day)
        self.assertEqual(jack.personal.n_arrests, 5)
        return jack

    def test_assignment(self):
        import datetime
        today = datetime.date.today()
        jack = self.test_construction()
        jack.personal.nsa_data.date_of_contact = today
        self.assertEqual(jack.personal.nsa_data.date_of_contact, today)

    def test_invalid_assignment(self):
        import colander
        jack = self.test_construction()
        with self.assertRaises(colander.Invalid):
            jack.personal = 'foo'

    def test_assignment_of_appdata(self):
        import datetime
        today = datetime.date.today()
        jack = self.test_construction()
        jack.personal.nsa_data = {
            'serialnum': 'def456', 'date_of_contact': today}
        self.assertEqual(jack.personal.nsa_data.serialnum, 'def456')
        self.assertEqual(jack.personal.nsa_data.date_of_contact, today)

    def test_assignment_of_appdata_extra_params(self):
        import colander
        import datetime
        today = datetime.date.today()
        jack = self.test_construction()
        with self.assertRaises(TypeError):
            jack.personal.nsa_data = {
                'serialnum': 'def456', 'date_of_contact': today, 'foo': 'bar'}

    def test_validation(self):
        import colander
        jack = self.test_construction()
        with self.assertRaises(colander.Invalid):
            jack.personal.nsa_data.date_of_contact = 'Christmas'

    def test_assignment_of_appdata_validation(self):
        jack = self.test_construction()
        with self.assertRaises(colander.Invalid) as ecm:
            jack.personal.nsa_data = {'date_of_contact': 'Christmas'}
        self.assertEqual(ecm.exception.asdict(), {
            'nsa_data.date_of_contact': u'"Christmas" is not a date object',
            'nsa_data.serialnum': u'Required'})

    def test_non_schema_attributes(self):
        jack = self.test_construction()
        with self.assertRaises(AttributeError):
            foo = jack.personal.phone_number
        jack.personal.phone_number = '555-1212'
        self.assertEqual(jack.personal.phone_number, '555-1212')

    def test_serialize(self):
        jack = self.test_construction()
        self.assertEquals(jack.serialize(), {
            'name': 'Jack',
            'age': '500',
            'personal': {
                'nsa_data': {
                    'serialnum': 'abc123',
                    'date_of_contact': '2010-05-12',
                },
                'n_arrests': '5',
            },
        })

    def test_deserialize(self):
        from datetime import date
        jonas = self.content_type.deserialize({
            'name': 'Jonas',
            'age': '50',
            'personal': {
                'nsa_data': {
                    'serialnum': 'a1',
                    'date_of_contact': '2011-05-12',
                },
                'n_arrests': '6',
            },
        })
        self.assertEqual(jonas.name, 'Jonas')
        self.assertEqual(jonas.age, 50)
        self.assertEqual(jonas.personal.nsa_data.serialnum, 'a1')
        self.assertEqual(jonas.personal.nsa_data.date_of_contact,
                         date(2011, 5, 12))
        self.assertEqual(jonas.personal.n_arrests, 6)


class NestedSequenceNodeTests(unittest2.TestCase):

    def setUp(self):
        import colander
        from limone import Limone

        limone = Limone()

        class Y(colander.SequenceSchema):
            y = colander.SchemaNode(colander.Int())

        class X(colander.SequenceSchema):
            x = Y()

        class Plane(colander.Schema):
            id = colander.SchemaNode(colander.Str('UTF-8'), default='plane')
            coords = X()

        @limone.content_type(Plane)
        class PlaneType(object):
            foo = 'bar'

        self.content_type = PlaneType

    def test_construction(self):
        plane = self.content_type(coords=[[1, 2, 3],
                                          [4, 5, 6],
                                          [7, 8, 9]])
        self.assertEqual(plane.coords[0][0], 1)
        self.assertEqual(plane.coords[0][1], 2)
        self.assertEqual(plane.coords[0][2], 3)
        self.assertEqual(plane.coords[1][0], 4)
        self.assertEqual(plane.coords[1][1], 5)
        self.assertEqual(plane.coords[1][2], 6)
        self.assertEqual(plane.coords[2][0], 7)
        self.assertEqual(plane.coords[2][1], 8)
        self.assertEqual(plane.coords[2][2], 9)
        self.assertEqual(plane.id, 'plane')
        self.assertEqual(plane.foo, 'bar')
        return plane

    def test_comparison(self):
        plane = self.test_construction()
        coords = plane.coords[1]
        self.assertLess(coords, [4, 5, 6, 7])
        self.assertLess(coords, [5, 6, 7])
        self.assertGreater(coords, [1, 2, 3])
        self.assertEqual(coords, [4, 5, 6])

    def test_repr(self):
        plane = self.test_construction()
        self.assertEqual(repr(plane.coords),
                         '[[1, 2, 3], [4, 5, 6], [7, 8, 9]]')

    def test_assignment(self):
        plane = self.test_construction()
        plane.coords[1][1] = 45
        self.assertEqual(plane.coords[1][1], 45)

    def test_validation(self):
        import colander
        plane = self.test_construction()
        with self.assertRaises(colander.Invalid):
            plane.coords[1][1] = 'forty five'

    def test_assign_appstruct(self):
        plane = self.test_construction()
        plane.coords[1] = [45, 46, 47]
        self.assertEqual(plane.coords[1], [45, 46, 47])

    def test_assign_appstruct_invalid(self):
        import colander
        plane = self.test_construction()
        with self.assertRaises(colander.Invalid) as ecm:
            plane.coords[1] = ['one', 2, 'three']
        self.assertEqual(
            ecm.exception.asdict(), {
            'x.0': u'"one" is not a number', 'x.2': u'"three" is not a number'}
        )

    def test_serialize(self):
        plane = self.test_construction()
        self.assertEqual(plane.serialize(), {
            'coords': [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9']],
            'id': 'plane'
        })

    def test_deserialization(self):
        plane = self.content_type.deserialize({
            'coords': [['9', '8', '7'], ['6', '5']],
            'id': 'test'})
        self.assertEqual(plane.coords, [[9, 8, 7], [6, 5]])

    def test_append(self):
        import colander
        plane = self.test_construction()
        plane.coords[0].append(4)
        self.assertEqual(plane.coords[0], [1, 2, 3, 4])
        with self.assertRaises(colander.Invalid):
            plane.coords.append(6)

    def test_extend(self):
        import colander
        plane = self.test_construction()
        plane.coords[0].extend([4, 5])
        self.assertEqual(plane.coords[0], [1, 2, 3, 4, 5])
        with self.assertRaises(colander.Invalid):
            plane.coords.extend([1, 2])

    def test_count(self):
        plane = self.test_construction()
        self.assertEqual(plane.coords[0].count(2), 1)

    def test_index(self):
        plane = self.test_construction()
        coords = plane.coords[0]
        self.assertEqual(coords.index(2), 1)
        with self.assertRaises(ValueError):
            coords.index(2, 0, 1)

    def test_insert(self):
        import colander
        plane = self.test_construction()
        plane.coords[0].insert(1, 8)
        self.assertEqual(plane.coords[0], [1, 8, 2, 3])
        with self.assertRaises(colander.Invalid):
            plane.coords.insert(1, 1)

    def test_pop(self):
        plane = self.test_construction()
        self.assertEqual(plane.coords[0].pop(0), 1)
        self.assertEqual(plane.coords[0], [2, 3])

    def test_remove(self):
        plane = self.test_construction()
        plane.coords[0].remove(2)
        self.assertEqual(plane.coords[0], [1, 3])

    def test_reverse(self):
        plane = self.test_construction()
        plane.coords[0].reverse()
        self.assertEqual(plane.coords[0], [3, 2, 1])

    def test_getslice(self):
        plane = self.test_construction()
        self.assertEqual(plane.coords[0][1:3], [2, 3])

    def test_setslice(self):
        import colander
        plane = self.test_construction()
        plane.coords[0][1:3] = [6, 7, 8]
        self.assertEqual(plane.coords[0], [1, 6, 7, 8])
        with self.assertRaises(colander.Invalid) as ecm:
            plane.coords[0][1:3] = ['six', 'seven', 'eight']
        self.assertEqual(ecm.exception.asdict(), {
            'x.1': u'"six" is not a number',
            'x.2': u'"seven" is not a number',
            'x.3': u'"eight" is not a number'})

    def test_delslice(self):
        plane = self.test_construction()
        del plane.coords[0][1:3]
        self.assertEqual(plane.coords[0], [1])

    def test_contains(self):
        plane = self.test_construction()
        self.assertTrue(2 in plane.coords[0])


import colander
from limone import Limone as Limone
limone = Limone()

@limone.content_schema
class Cat(colander.Schema):
    fur = colander.SchemaNode(colander.String('UTF-8'))

class TestTypesAtModuleScopeDontNeedImportHooks(unittest2.TestCase):

    def test_module_and_name_are_correct(self):
        self.assertEqual(Cat.__module__, 'limone.tests')
        self.assertEqual(Cat.__name__, 'Cat')

    def test_can_pickle_instance(self):
        import pickle
        lily = Cat(fur='tabby')
        lily = pickle.loads(pickle.dumps(lily))
        self.assertEqual(lily.fur, 'tabby')

    def test_can_pickle_type(self):
        import pickle
        ct = pickle.loads(pickle.dumps(Cat))
        self.assertEqual(ct.__schema__.children[0].name, 'fur')
