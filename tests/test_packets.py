import unittest
from packets import DBField
from construct import Container


class PacketsTestCase(unittest.TestCase):
    def test_string_parsing(self):
        field = DBField.parse(
            b"\x26\x00\x00\x00\x0a\xff\xfa\x00\x48\x00\x49\x00" +
            b"\x53\x00\x54\x00\x4f\x00\x52\x00\x59\xff\xfb\x00\x00"
        )

        self.assertEqual(
            field,
            Container(type='string')(value="\ufffaHISTORY\ufffb"),
        )

        field = DBField.parse(
            b"\x26\x00\x00\x00\x0b\xff\xfa\x00\x50\x00\x4c\x00" +
            b"\x41\x00\x59\x00\x4c\x00\x49\x00\x53\x00\x54\xff\xfb" +
            b"\x00\x00"
        )

        self.assertEqual(
            field,
            Container(type='string')(value="\ufffaPLAYLIST\ufffb"),
        )
