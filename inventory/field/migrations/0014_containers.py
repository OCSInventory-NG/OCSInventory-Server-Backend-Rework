from django.db import migrations


def create_containers_fields(apps, schema_editor):
    Field = apps.get_model("field", "Field")
    Section = apps.get_model("section", "Section")
    Template = apps.get_model("template", "Template")

    linux_fields = {
        "CONTAINERS": [
            ("RUNTIME", "Runtime: (.*)"),
            ("NAME", "Name: /?(.*)"),
            ("ID", "Id: (.*)"),
            ("IMAGE", "Image: ([^\\s@]+?)(?::[\\w][\\w.-]*)?(?:@\\S+)?\\r?\\n"),
            ("TAG", "Image: [^\\s@]+?:([\\w][\\w.-]*)(?:@\\S+)?\\r?\\n"),
            ("STATE", "State: (.*)"),
            ("CREATED", "Created: (.*)"),
            ("PORTS", "Ports: (.*)"),
            ("MOUNTS", "Mounts: (.*)"),
            ("COMPOSE PROJECT", "Compose project: (.*)"),
            ("WORKING DIR", "Working dir: (.*)"),
            ("COMPOSE FILES", "Compose files: (.*)"),
        ],
        "CONTAINER SOFTWARES": [
            ("CONTAINER", "Container: (.*)"),
            ("NAME", "Name: (.*)"),
            ("VERSION", "Version: (.*)"),
        ],
    }

    windows_fields = {
        "CONTAINERS": [
            ("RUNTIME", "Runtime"),
            ("NAME", "Name"),
            ("ID", "Id"),
            ("IMAGE", "Image"),
            ("TAG", "Tag"),
            ("STATE", "State"),
            ("CREATED", "Created"),
            ("PORTS", "Ports"),
            ("MOUNTS", "Mounts"),
            ("COMPOSE PROJECT", "ComposeProject"),
            ("WORKING DIR", "WorkingDir"),
            ("COMPOSE FILES", "ComposeFiles"),
        ],
        "CONTAINER SOFTWARES": [
            ("CONTAINER", "Container"),
            ("NAME", "Name"),
            ("VERSION", "Version"),
        ],
    }

    templates_fields = [
        (
            Template.objects.get(name="Linux Extended (Debian based)", os="DEB"),
            linux_fields,
        ),
        (
            Template.objects.get(name="Linux Extended (RHEL based)", os="RHEL"),
            linux_fields,
        ),
        (Template.objects.get(name="Windows Extended", os="WIN"), windows_fields),
    ]

    for template, sections_fields in templates_fields:
        for section_name, fields in sections_fields.items():
            section = Section.objects.get(name=section_name, template=template)

            for order, (name, retrieval_value) in enumerate(fields, start=1):
                try:
                    Field.objects.create(
                        name=name,
                        order=order,
                        retrieval_value=retrieval_value,
                        override_target=False,
                        new_target=None,
                        retrieval_method=None,
                        retrieval_output=None,
                        options=None,
                        section=section,
                    )
                except Exception as e:
                    print(e)


class Migration(migrations.Migration):
    dependencies = [
        ("section", "0015_containers"),
        ("field", "0013_linux_extended_rhel"),
    ]

    operations = [
        migrations.RunPython(create_containers_fields),
    ]
