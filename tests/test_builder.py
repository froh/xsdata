from types import GeneratorType
from unittest.mock import PropertyMock, call, patch

from tests.factories import (
    AttrFactory,
    AttrTypeFactory,
    ClassFactory,
    ExtensionFactory,
    FactoryTestCase,
)
from xsdata.builder import ClassBuilder
from xsdata.models.codegen import Attr
from xsdata.models.elements import (
    Attribute,
    AttributeGroup,
    ComplexContent,
    ComplexType,
    Element,
    Enumeration,
    Extension,
    Group,
    Restriction,
    Schema,
    Sequence,
    SimpleContent,
    SimpleType,
)
from xsdata.models.enums import FormType, TagType, XSDType


class ClassBuilderTests(FactoryTestCase):
    def setUp(self) -> None:
        super(ClassBuilderTests, self).setUp()
        self.schema = Schema.create()
        self.builder = ClassBuilder(schema=self.schema)

    @patch.object(ClassBuilder, "build_class")
    def test_process(self, mock_build_class):
        for _ in range(2):
            self.schema.simple_types.append(SimpleType.create())
            self.schema.attribute_groups.append(AttributeGroup.create())
            self.schema.groups.append(Group.create())
            self.schema.attributes.append(Attribute.create())
            self.schema.complex_types.append(ComplexType.create())
            self.schema.elements.append(Element.create())

        mock_build_class.side_effect = classes = ClassFactory.list(12)

        self.assertEqual(classes, self.builder.build())
        mock_build_class.assert_has_calls(
            [
                call(self.schema.simple_types[0]),
                call(self.schema.simple_types[1]),
                call(self.schema.attribute_groups[0]),
                call(self.schema.attribute_groups[1]),
                call(self.schema.groups[0]),
                call(self.schema.groups[1]),
                call(self.schema.attributes[0]),
                call(self.schema.attributes[1]),
                call(self.schema.complex_types[0]),
                call(self.schema.complex_types[1]),
                call(self.schema.elements[0]),
                call(self.schema.elements[1]),
            ]
        )

    def test_element_namespace(self):
        self.schema.nsmap["foo"] = "bar"
        self.schema.target_namespace = "foobar"

        element = Element.create(ref="foo:something")
        self.assertEqual("bar", self.builder.element_namespace(element))

        element = Element.create(form=FormType.QUALIFIED)
        self.assertEqual("foobar", self.builder.element_namespace(element))

        element = Element.create()
        self.assertEqual("", self.builder.element_namespace(element))

        attribute = Attribute.create()
        self.assertIsNone(self.builder.element_namespace(attribute))

    @patch.object(ClassBuilder, "element_namespace")
    @patch.object(ClassBuilder, "build_class_attributes")
    @patch.object(ClassBuilder, "build_class_extensions")
    @patch.object(Element, "is_abstract", new_callable=PropertyMock)
    @patch.object(Element, "display_help", new_callable=PropertyMock)
    @patch.object(Element, "real_name", new_callable=PropertyMock)
    def test_build_class(
        self,
        mock_real_name,
        mock_display_help,
        mock_is_abstract,
        mock_build_class_extensions,
        mock_build_class_attributes,
        mock_element_namespace,
    ):
        extensions = ExtensionFactory.list(2)
        mock_real_name.return_value = "name"
        mock_display_help.return_value = "sos"
        mock_is_abstract.return_value = True
        mock_build_class_extensions.return_value = extensions
        mock_element_namespace.return_value = "foo:name"

        element = Element.create()
        result = self.builder.build_class(element)

        mock_build_class_attributes.assert_called_once_with(element, result)
        mock_element_namespace.assert_called_once_with(element)

        expected = ClassFactory.create(
            name="name",
            type=Element,
            extensions=extensions,
            help="sos",
            is_abstract=True,
            namespace="foo:name",
        )
        self.assertEqual(expected, result)

    @patch.object(ClassBuilder, "default_value_type")
    @patch.object(ClassBuilder, "build_class_attribute")
    def test_build_class_attributes_without_default_value_type(
        self, mock_build_class_attribute, default_value_type
    ):
        default_value_type.return_value = None
        element = Element.create(
            complex_type=ComplexType.create(
                attributes=[Attribute.create(), Attribute.create()]
            )
        )
        item = ClassFactory.create()

        self.builder.build_class_attributes(element, item)

        mock_build_class_attribute.assert_has_calls(
            [call(item, attr) for attr in element.complex_type.attributes]
        )

        self.assertEqual(0, len(item.attrs))

    @patch.object(ClassBuilder, "default_value_type")
    @patch.object(ClassBuilder, "build_class_attribute")
    def test_build_class_attributes_with_default_value_type(
        self, mock_build_class_attribute, default_value_type
    ):
        default_value_type.return_value = "xs:string"
        element = Element.create()
        item = ClassFactory.create()

        self.builder.build_class_attributes(element, item)

        mock_build_class_attribute.assert_not_called()

        expected = Attr(
            index=0,
            name="value",
            default=None,
            types=AttrTypeFactory.list(1, name=XSDType.STRING.code),
            local_type=TagType.EXTENSION.cname,
        )
        self.assertEqual(1, len(item.attrs))
        self.assertEqual(expected, item.attrs[0])

    @patch.object(ClassBuilder, "element_extensions")
    def test_build_class_extensions(self, mock_element_extensions):
        bar = ExtensionFactory.create(name="bar", index=3)
        bar_dub = ExtensionFactory.create(name="bar", index=2)
        foo = ExtensionFactory.create(name="foo", index=1)

        mock_element_extensions.return_value = [bar, bar_dub, foo]

        element = Element.create()
        actual = self.builder.build_class_extensions(element)

        self.assertEqual([bar_dub, foo], actual)

    def test_element_children(self):
        complex_type = ComplexType.create(
            attributes=[Attribute.create() for i in range(2)],
            sequence=Sequence.create(
                elements=[Element.create() for i in range(2)]
            ),
            simple_content=SimpleContent.create(
                restriction=Restriction.create()
            ),
            complex_content=ComplexContent.create(
                restriction=Restriction.create(
                    enumerations=[Enumeration.create(value=x) for x in "abc"]
                )
            ),
        )

        children = self.builder.element_children(complex_type)
        expected = [
            complex_type.simple_content.restriction,
            complex_type.complex_content.restriction.enumerations[0],
            complex_type.complex_content.restriction.enumerations[1],
            complex_type.complex_content.restriction.enumerations[2],
            complex_type.sequence.elements[0],
            complex_type.sequence.elements[1],
            complex_type.attributes[0],
            complex_type.attributes[1],
        ]
        self.assertIsInstance(children, GeneratorType)
        self.assertEqual(expected, list(children))

    def test_element_extensions(self):
        self.builder.target_prefix = "bk:"
        complex_type = ComplexType.create(
            attributes=[Attribute.create(index=i) for i in range(2)],
            sequence=Sequence.create(
                groups=[
                    Group.create(ref="a", index=3),
                    Group.create(ref="bk:b", index=4),
                    Group.create(ref="c", index=5),
                ]
            ),
            simple_content=SimpleContent.create(
                restriction=Restriction.create(base="isAttribute")
            ),
            complex_content=ComplexContent.create(
                extension=Extension.create(
                    base="bk:ext", index=7, type="Extension"
                )
            ),
        )

        children = self.builder.element_extensions(complex_type)
        expected = [
            ExtensionFactory.create(name="bk:ext", index=7, type="Extension"),
            ExtensionFactory.create(name="a", index=3, type="Group"),
            ExtensionFactory.create(name="bk:b", index=4, type="Group"),
            ExtensionFactory.create(name="c", index=5, type="Group"),
        ]

        self.assertIsInstance(children, GeneratorType)
        self.assertEqual(expected, list(children))

    def test_element_extensions_with_typed_parent(self):
        self.builder.target_prefix = "bk:"
        element = Element.create(type="bk:book", index=23)
        children = self.builder.element_extensions(element)
        expected = ExtensionFactory.list(
            1, name="bk:book", index=0, type="Element"
        )

        self.assertEqual(expected, list(children))

    @patch.object(ClassBuilder, "build_class_attribute_types")
    @patch.object(ClassBuilder, "element_namespace")
    @patch.object(Attribute, "get_restrictions")
    @patch.object(Attribute, "prefix", new_callable=PropertyMock)
    @patch.object(Attribute, "display_help", new_callable=PropertyMock)
    @patch.object(Attribute, "real_name", new_callable=PropertyMock)
    def test_build_class_attribute(
        self,
        mock_real_name,
        mock_display_help,
        mock_prefix_property,
        mock_get_restrictions,
        mock_element_namespace,
        mock_build_class_attribute_types,
    ):
        item = ClassFactory.create()

        mock_build_class_attribute_types.return_value = AttrTypeFactory.list(
            1, name="xs:int"
        )
        mock_real_name.return_value = item.name
        mock_display_help.return_value = "sos"
        mock_prefix_property.return_value = "com"
        mock_element_namespace.return_value = "http://something/common"
        mock_get_restrictions.return_value = {"required": True}

        attribute = Attribute.create(default="false", index=66)

        self.builder.build_class_attribute(item, attribute)
        expected = AttrFactory.create(
            name=mock_real_name.return_value,
            types=mock_build_class_attribute_types.return_value,
            local_type=Attribute.__name__,
            namespace=mock_element_namespace.return_value,
            help=mock_display_help.return_value,
            default="false",
            index=66,
            **mock_get_restrictions.return_value,
        )
        self.assertEqual(expected, item.attrs[0])
        mock_build_class_attribute_types.assert_called_once_with(
            item, attribute
        )
        mock_element_namespace.assert_called_once_with(attribute)

    @patch.object(ClassBuilder, "build_class_attribute_types")
    @patch.object(Attribute, "real_name", new_callable=PropertyMock)
    def test_build_class_attribute_raises_exception_when_empty_types(
        self, mock_real_name, mock_build_class_attribute_types
    ):
        item = ClassFactory.create()

        mock_build_class_attribute_types.return_value = []
        mock_real_name.return_value = "quantity"

        attribute = Attribute.create(default="false", index=66)

        with self.assertRaises(ValueError) as cm:
            self.builder.build_class_attribute(item, attribute)

        msg = f"Failed to detect type for attribute: class_B.quantity"
        self.assertEqual(msg, str(cm.exception))

    @patch.object(Attribute, "real_type", new_callable=PropertyMock)
    @patch.object(ClassBuilder, "build_inner_class")
    def test_build_class_attribute_types(
        self, mock_build_inner_class, mock_real_type
    ):
        mock_real_type.return_value = " xs:int  xs:str "
        mock_build_inner_class.return_value = None

        item = ClassFactory.create()
        attribute = Attribute.create(default="false", index=66)
        expected = self.builder.build_class_attribute_types(item, attribute)

        actual = [
            AttrTypeFactory.create(name="xs:int"),
            AttrTypeFactory.create(name="xs:str"),
        ]

        self.assertEqual(actual, expected)

    @patch.object(Attribute, "real_type", new_callable=PropertyMock)
    @patch.object(ClassBuilder, "build_inner_class")
    def test_build_class_attribute_types_when_obj_has_inner_class(
        self, mock_build_inner_class, mock_real_type
    ):
        inner_class = ClassFactory.create(name="foo")
        mock_real_type.return_value = " xs:int  xs:str "
        mock_build_inner_class.return_value = inner_class

        item = ClassFactory.create()
        attribute = Attribute.create(default="false", index=66)
        expected = self.builder.build_class_attribute_types(item, attribute)

        actual = [
            AttrTypeFactory.create(name="xs:int"),
            AttrTypeFactory.create(name="xs:str"),
            AttrTypeFactory.create(name="foo", forward_ref=True),
        ]

        self.assertEqual(actual, expected)
        self.assertEqual([inner_class], item.inner)

    @patch.object(Attribute, "real_type", new_callable=PropertyMock)
    @patch.object(ClassBuilder, "build_inner_class")
    def test_build_class_attribute_types_when_obj_has_no_types(
        self, mock_build_inner_class, mock_real_type
    ):
        mock_real_type.return_value = None
        mock_build_inner_class.return_value = None

        item = ClassFactory.create()
        attribute = Attribute.create(default="false", index=66)
        expected = self.builder.build_class_attribute_types(item, attribute)

        self.assertEqual([], expected)

    @patch.object(ClassBuilder, "build_class")
    @patch.object(ClassBuilder, "has_anonymous_class")
    def test_build_inner_class_when_has_anonymous_class(
        self, mock_has_anonymous_class, mock_build_class,
    ):
        inner_class = ClassFactory.create()
        mock_build_class.return_value = inner_class
        mock_has_anonymous_class.return_value = True

        complex_type = ComplexType.create()
        element = Element.create(name="foo", complex_type=complex_type)

        self.assertEqual(inner_class, self.builder.build_inner_class(element))
        self.assertIsNone(element.complex_type)
        self.assertEqual("foo", complex_type.name)

    @patch.object(ClassBuilder, "build_class")
    @patch.object(ClassBuilder, "has_anonymous_enumeration")
    @patch.object(ClassBuilder, "has_anonymous_class")
    def test_build_inner_class_when_has_anonymous_enumeration(
        self,
        mock_has_anonymous_class,
        mock_has_anonymous_enumeration,
        mock_build_class,
    ):
        inner_class = ClassFactory.create()
        mock_build_class.return_value = inner_class
        mock_has_anonymous_class.return_value = False
        mock_has_anonymous_enumeration.return_value = True

        simple_type = SimpleType.create()
        element = Element.create(
            name="foo", simple_type=simple_type, type="xs:int"
        )

        self.assertEqual(inner_class, self.builder.build_inner_class(element))
        self.assertIsNone(element.simple_type)
        self.assertIsNone(element.type)
        self.assertEqual("foo", simple_type.name)

    def test_has_anonymous_class(self):
        obj = Element.create()
        self.assertFalse(self.builder.has_anonymous_class(obj))

        obj = Element.create(type="foo")
        self.assertFalse(self.builder.has_anonymous_class(obj))

        obj = Element.create(complex_type=ComplexType.create())
        self.assertTrue(self.builder.has_anonymous_class(obj))

        obj = Attribute.create()
        self.assertFalse(self.builder.has_anonymous_class(obj))

    def test_has_anonymous_enumeration(self):
        for clazz in [Element, Attribute]:
            obj = clazz.create()
            self.assertFalse(self.builder.has_anonymous_enumeration(obj))

            obj = clazz.create(simple_type=SimpleType.create())
            self.assertFalse(self.builder.has_anonymous_enumeration(obj))

            obj.simple_type.restriction = Restriction.create()
            self.assertFalse(self.builder.has_anonymous_enumeration(obj))

            obj.simple_type.restriction.enumerations.append(
                Enumeration.create()
            )
            self.assertTrue(self.builder.has_anonymous_enumeration(obj))

            obj.type = "foo"
            self.assertFalse(self.builder.has_anonymous_enumeration(obj))

    @patch("xsdata.builder.logger.warning")
    def test_default_value_type(self, mock_logger_warning):
        item = ClassFactory.create()
        self.assertEqual("xs:string", ClassBuilder.default_value_type(item))

        item = ClassFactory.create(extensions=ExtensionFactory.list(1))
        self.assertIsNone(ClassBuilder.default_value_type(item))

        item = ClassFactory.create(
            extensions=[
                ExtensionFactory.create(name="xs:int"),
                ExtensionFactory.create(name="xs:boolean"),
            ]
        )
        self.assertEqual(
            "xs:int xs:boolean", ClassBuilder.default_value_type(item)
        )
        self.assertEqual(0, len(item.extensions))

        item = ClassFactory.create(
            attrs=AttrFactory.list(2, local_type=TagType.ENUMERATION.cname),
            extensions=ExtensionFactory.list(1, name="xs:int"),
        )

        self.assertIsNone(ClassBuilder.default_value_type(item))
        mock_logger_warning.assert_called_once_with("Empty class: `class_B`")
