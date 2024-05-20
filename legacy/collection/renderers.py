from django.utils.xmlutils import SimplerXMLGenerator
from io import StringIO
from rest_framework_xml.renderers import XMLRenderer
import xml.dom.minidom
import zlib


class LegacyXMLRenderer(XMLRenderer):
    root_tag_name = "REPLY"

    def render(self, data, media_type=None, renderer_context=None):
        if data is None:
            return ""

        stream = StringIO()

        xmlGenerator = SimplerXMLGenerator(stream, self.charset)
        xmlGenerator.startDocument()
        xmlGenerator.startElement(self.root_tag_name, {})

        self._to_xml(xmlGenerator, data)

        xmlGenerator.endElement(self.root_tag_name)
        xmlGenerator.endDocument()

        raw_xml = stream.getvalue()
        dom = xml.dom.minidom.parseString(raw_xml)
        pretty_xml = dom.toprettyxml(indent="   ")

        return zlib.compress(pretty_xml.encode("utf-8"))
        # Remove the compression if you are debugging
        # return pretty_xml
