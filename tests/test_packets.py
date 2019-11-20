import unittest
from prodj.network.packets import DBField, DBMessage
from construct import Container

class PacketsTestCase(unittest.TestCase):
    def test_string_parsing(self):
        self.assertEqual(
            DBField.parse(
                b"\x26\x00\x00\x00\x0a\xff\xfa\x00\x48\x00\x49\x00" +
                b"\x53\x00\x54\x00\x4f\x00\x52\x00\x59\xff\xfb\x00\x00"
            ),
            Container(type='string')(value="\ufffaHISTORY\ufffb"),
        )

        self.assertEqual(
            DBField.parse(
                b"\x26\x00\x00\x00\x0b\xff\xfa\x00\x50\x00\x4c\x00" +
                b"\x41\x00\x59\x00\x4c\x00\x49\x00\x53\x00\x54\xff\xfb" +
                b"\x00\x00"
            ),
            Container(type='string')(value="\ufffaPLAYLIST\ufffb"),
        )

        self.assertEqual(
            DBField.parse(bytes([
                0x26, 0x00, 0x00, 0x00, 0x09, 0xff, 0xfa, 0x00, 0x41,
                0x00, 0x52, 0x00, 0x54, 0x00, 0x49, 0x00, 0x53,
                0x00, 0x54, 0xff, 0xfb, 0x00, 0x00,
            ])),
            Container(type='string')(value="\ufffaARTIST\ufffb"))

    def test_building_root_menu_request_menu_item_part(self):
        data = bytes([
            0x11, 0x87, 0x23, 0x49, 0xae,
            0x11, 0x05, 0x80, 0x00, 0x01,
            0x10, 0x41, 0x01,
            0x0f, 0x0c, 0x14, 0x00, 0x00, 0x00, 0x0c, 0x06, 0x06, 0x06, 0x02,
            0x06, 0x02, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x16,
            0x11, 0x00, 0x00, 0x00, 0x14,
            0x26, 0x00, 0x00, 0x00, 0x09, 0xff, 0xfa, 0x00, 0x41,
            0x00, 0x52, 0x00, 0x54, 0x00, 0x49, 0x00, 0x53,
            0x00, 0x54, 0xff, 0xfb, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x02,
            0x26, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x95,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x00,
            0x11, 0x00, 0x00, 0x00, 0x00,
        ])

        message = DBMessage.parse(data)

        self.assertEqual(message.type, 'menu_item')
        self.assertEqual(
            message,
            (Container
                (magic=2267236782)
                (transaction_id=92274689)
                (type='menu_item')
                (argument_count=12)
                (arg_types=[
                    'int32', 'int32', 'int32', 'string', 'int32', 'string',
                    'int32', 'int32', 'int32', 'int32', 'int32', 'int32',
                ])
                (args=[
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=22),
                    Container(type='int32')(value=20),
                    Container(type='string')(value='\ufffaARTIST\ufffb'),
                    Container(type='int32')(value=2),
                    Container(type='string')(value=''),
                    Container(type='int32')(value=149),
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=0),
                    Container(type='int32')(value=0),
                ])
             )
        )
