from unittest import mock

from xsdata.codegen.container import ClassContainer
from xsdata.codegen.handlers import RenameDuplicateClasses
from xsdata.models.config import GeneratorConfig, StructureStyle
from xsdata.models.enums import Tag
from xsdata.utils.testing import (
    AttrFactory,
    AttrTypeFactory,
    ClassFactory,
    ExtensionFactory,
    FactoryTestCase,
)


class RenameDuplicateClassesTests(FactoryTestCase):
    def setUp(self):
        super().setUp()

        self.container = ClassContainer(config=GeneratorConfig())
        self.processor = RenameDuplicateClasses(container=self.container)

    @mock.patch.object(RenameDuplicateClasses, "merge_classes")
    @mock.patch.object(RenameDuplicateClasses, "rename_classes")
    def test_run(self, mock_rename_classes, mock_merge_classes):
        classes = [
            ClassFactory.create(qname="{foo}A"),
            ClassFactory.create(qname="{foo}a"),
            ClassFactory.create(qname="_a"),
            ClassFactory.create(qname="_b"),
            ClassFactory.create(qname="b", location="!@#$"),
        ]
        self.container.extend(classes)
        self.processor.run()

        mock_rename_classes.assert_has_calls(
            [
                mock.call(classes[:2], False),
                mock.call(classes[3:], False),
            ]
        )
        self.assertEqual(0, mock_merge_classes.call_count)

    @mock.patch.object(RenameDuplicateClasses, "merge_classes")
    @mock.patch.object(RenameDuplicateClasses, "rename_classes")
    def test_run_with_single_package_structure(
        self, mock_rename_classes, mock_merge_classes
    ):
        classes = [
            ClassFactory.create(qname="{foo}a"),
            ClassFactory.create(qname="{bar}a"),
            ClassFactory.create(qname="a"),
        ]
        self.container.extend(classes)
        self.processor.run()

        mock_rename_classes.assert_called_once_with(classes, True)
        self.assertEqual(0, mock_merge_classes.call_count)

    @mock.patch.object(RenameDuplicateClasses, "merge_classes")
    @mock.patch.object(RenameDuplicateClasses, "rename_classes")
    def test_run_with_single_location_source(
        self, mock_rename_classes, mock_merge_classes
    ):
        classes = [
            ClassFactory.create(qname="{foo}a"),
            ClassFactory.create(qname="{bar}a"),
            ClassFactory.create(qname="a"),
        ]

        self.container.config.output.structure_style = StructureStyle.SINGLE_PACKAGE
        self.container.extend(classes)
        self.processor.run()

        mock_rename_classes.assert_called_once_with(classes, True)
        self.assertEqual(0, mock_merge_classes.call_count)

    @mock.patch.object(RenameDuplicateClasses, "merge_classes")
    @mock.patch.object(RenameDuplicateClasses, "rename_classes")
    def test_run_with_clusters_structure(self, mock_rename_classes, mock_merge_classes):
        classes = [
            ClassFactory.create(qname="{foo}a"),
            ClassFactory.create(qname="{bar}a"),
            ClassFactory.create(qname="a"),
        ]
        self.container.config.output.structure_style = StructureStyle.CLUSTERS
        self.container.extend(classes)
        self.processor.run()

        mock_rename_classes.assert_called_once_with(classes, True)
        self.assertEqual(0, mock_merge_classes.call_count)

    @mock.patch.object(RenameDuplicateClasses, "merge_classes")
    @mock.patch.object(RenameDuplicateClasses, "rename_classes")
    def test_run_with_same_classes(self, mock_rename_classes, mock_merge_classes):
        first = ClassFactory.create()
        second = first.clone()
        third = ClassFactory.create()

        self.container.extend([first, second, third])
        self.processor.run()

        self.assertEqual(0, mock_rename_classes.call_count)
        mock_merge_classes.assert_called_once_with([first, second])

    @mock.patch.object(RenameDuplicateClasses, "update_class_references")
    def test_merge_classes(self, mock_update_class_references):
        first = ClassFactory.create()
        second = first.clone()
        third = first.clone()
        fourth = ClassFactory.create()
        fifth = ClassFactory.create()

        self.container.extend([first, second, third, fourth, fifth])
        self.processor.run()

        search = {first.ref, second.ref}
        replace = third.ref

        mock_update_class_references.assert_has_calls(
            [
                mock.call(first, search, replace),
                mock.call(fourth, search, replace),
                mock.call(fifth, search, replace),
            ]
        )
        self.assertEqual([first, fourth, fifth], list(self.container))

    def test_update_class_references(self):
        replacements = {1, 2, 3, 4}
        target = ClassFactory.create(
            attrs=AttrFactory.list(3),
            extensions=ExtensionFactory.list(2),
            inner=[ClassFactory.elements(2), ClassFactory.create()],
        )
        target.attrs[1].choices = AttrFactory.list(2)

        target.attrs[0].types[0].reference = 1
        target.attrs[1].choices[0].types[0].reference = 2
        target.extensions[1].type.reference = 3
        target.inner[0].attrs[0].types[0].reference = 4

        self.processor.update_class_references(target, replacements, 5)
        self.assertEqual([5, 5, 5, 5], list(target.references))

    @mock.patch.object(RenameDuplicateClasses, "add_numeric_suffix")
    def test_rename_classes(self, mock_add_numeric_suffix):
        classes = [
            ClassFactory.create(qname="_a", tag=Tag.ELEMENT),
            ClassFactory.create(qname="_A", tag=Tag.ELEMENT),
            ClassFactory.create(qname="a", tag=Tag.COMPLEX_TYPE),
        ]
        self.processor.rename_classes(classes, False)
        self.processor.rename_classes(classes, True)

        mock_add_numeric_suffix.assert_has_calls(
            [
                mock.call(classes[1], False),
                mock.call(classes[0], False),
                mock.call(classes[2], False),
                mock.call(classes[1], True),
                mock.call(classes[0], True),
                mock.call(classes[2], True),
            ]
        )

    @mock.patch.object(RenameDuplicateClasses, "add_abstract_suffix")
    def test_rename_classes_with_abstract_type(self, mock_add_abstract_suffix):
        classes = [
            ClassFactory.create(qname="_a", tag=Tag.ELEMENT),
            ClassFactory.create(qname="_A", tag=Tag.ELEMENT, abstract=True),
        ]
        self.processor.rename_classes(classes, True)

        mock_add_abstract_suffix.assert_called_once_with(classes[1])

    @mock.patch.object(RenameDuplicateClasses, "add_numeric_suffix")
    def test_rename_classes_protects_single_element(self, mock_rename_class):
        classes = [
            ClassFactory.create(qname="_a", tag=Tag.ELEMENT),
            ClassFactory.create(qname="a", tag=Tag.COMPLEX_TYPE),
        ]
        self.processor.rename_classes(classes, False)

        mock_rename_class.assert_called_once_with(classes[1], False)

    @mock.patch.object(RenameDuplicateClasses, "rename_class_dependencies")
    def test_add_numeric_suffix_by_slug(self, mock_rename_class_dependencies):
        target = ClassFactory.create(qname="{foo}_a")
        self.processor.container.add(target)
        self.processor.container.add(ClassFactory.create(qname="{foo}a_1"))
        self.processor.container.add(ClassFactory.create(qname="{foo}A_2"))
        self.processor.container.add(ClassFactory.create(qname="{bar}a_3"))
        self.processor.add_numeric_suffix(target, False)

        self.assertEqual("{foo}_a_3", target.qname)
        self.assertEqual("_a", target.meta_name)

        mock_rename_class_dependencies.assert_has_calls(
            mock.call(item, id(target), "{foo}_a_3")
            for item in self.processor.container
        )

        self.assertEqual([target], self.container.data["{foo}_a_3"])
        self.assertEqual([], self.container.data["{foo}_a"])

    @mock.patch.object(RenameDuplicateClasses, "rename_class_dependencies")
    def test_add_numeric_suffix_by_name(self, mock_rename_class_dependencies):
        target = ClassFactory.create(qname="{foo}_a")
        self.processor.container.add(target)
        self.processor.container.add(ClassFactory.create(qname="{bar}a_1"))
        self.processor.container.add(ClassFactory.create(qname="{thug}A_2"))
        self.processor.container.add(ClassFactory.create(qname="{bar}a_3"))
        self.processor.add_numeric_suffix(target, True)

        self.assertEqual("{foo}_a_4", target.qname)
        self.assertEqual("_a", target.meta_name)

        mock_rename_class_dependencies.assert_has_calls(
            mock.call(item, id(target), "{foo}_a_4")
            for item in self.processor.container
        )

        self.assertEqual([target], self.container.data["{foo}_a_4"])
        self.assertEqual([], self.container.data["{foo}_a"])

    def test_add_abstract_suffix(self):
        target = ClassFactory.create(qname="{xsdata}line", abstract=True)
        self.processor.container.add(target)

        self.processor.add_abstract_suffix(target)

        self.assertEqual("{xsdata}line_abstract", target.qname)
        self.assertEqual("line", target.meta_name)

    def test_rename_class_dependencies(self):
        attr_type = AttrTypeFactory.create(qname="{foo}bar", reference=1)

        target = ClassFactory.create(
            extensions=[
                ExtensionFactory.create(),
                ExtensionFactory.create(attr_type.clone()),
            ],
            attrs=[
                AttrFactory.create(),
                AttrFactory.create(types=[AttrTypeFactory.create(), attr_type.clone()]),
            ],
            inner=[
                ClassFactory.create(
                    extensions=[ExtensionFactory.create(attr_type.clone())],
                    attrs=[
                        AttrFactory.create(),
                        AttrFactory.create(
                            types=[AttrTypeFactory.create(), attr_type.clone()]
                        ),
                    ],
                )
            ],
        )

        self.processor.rename_class_dependencies(target, 1, "thug")
        dependencies = set(target.dependencies())
        self.assertNotIn("{foo}bar", dependencies)
        self.assertIn("thug", dependencies)

    def test_rename_attr_dependencies_with_default_enum(self):
        attr_type = AttrTypeFactory.create(qname="{foo}bar", reference=1)
        target = ClassFactory.create(
            attrs=[
                AttrFactory.create(
                    types=[attr_type],
                    default=f"@enum@{attr_type.qname}::member",
                ),
            ]
        )

        self.processor.rename_class_dependencies(target, 1, "thug")
        dependencies = set(target.dependencies())
        self.assertEqual("@enum@thug::member", target.attrs[0].default)
        self.assertNotIn("{foo}bar", dependencies)
        self.assertIn("thug", dependencies)

    def test_rename_attr_dependencies_with_choices(self):
        attr_type = AttrTypeFactory.create(qname="foo", reference=1)
        target = ClassFactory.create(
            attrs=[
                AttrFactory.create(
                    choices=[
                        AttrFactory.create(types=[attr_type.clone()]),
                    ]
                )
            ]
        )

        self.processor.rename_class_dependencies(target, 1, "bar")
        dependencies = set(target.dependencies())
        self.assertNotIn("foo", dependencies)
        self.assertIn("bar", dependencies)
