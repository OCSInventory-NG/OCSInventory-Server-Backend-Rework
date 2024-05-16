from io import StringIO
from django.utils.xmlutils import SimplerXMLGenerator
from rest_framework_xml.renderers import XMLRenderer
import zlib

class LegacyXMLRenderer(XMLRenderer):
    root_tag_name = "REPLY"

    def render(self, data, media_type=None, renderer_context=None):
        if data is None:
            return ""

        stream = StringIO()

        xml = SimplerXMLGenerator(stream, self.charset)
        xml.startDocument()
        xml.startElement(self.root_tag_name, {})

        self._to_xml(xml, data)

        xml.endElement(self.root_tag_name)
        xml.endDocument()
        return zlib.compress(stream.getvalue().encode())