import unittest
from prodj.pdblib.artist import Artist
from prodj.pdblib.page import AlignedPage

class ArtistPageTestCase(unittest.TestCase):
    def test_artist_row(self):
        data = bytes([
            0x60, 0x00, 0xe0, 0x03, 0x10, 0x03, 0x00, 0x00,
            0x03, 0x0a, 0x15, 0x41, 0x69, 0x72, 0x73, 0x74,
            0x72, 0x69, 0x6b, 0x65, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00
        ])
        parsed = Artist.parse(data)

        self.assertEqual(parsed.entry_start, 0)
        self.assertEqual(parsed.magic, 96)
        self.assertEqual(parsed.id, 784)
        self.assertEqual(parsed.name, u'Airstrike')

    def test_artist_page(self):
        file = open("tests/blobs/pdb_artists_common.bin", "rb")
        parsed = AlignedPage.parse_stream(file)

        self.assertEqual(parsed.index, 165)
        self.assertEqual(parsed.page_type, "block_artists")
        self.assertEqual(parsed.entry_count_small, 115)
        self.assertEqual(parsed.entry_count, 115)

        entries = 0
        for batch in parsed.entry_list:
            self.assertEqual(batch.entry_count, len(batch.entries))
            entries += batch.entry_count
        self.assertEqual(parsed.entry_count, entries)
        self.assertEqual(parsed.entry_count_small, entries)

        entry = parsed.entry_list[0].entries[0]
        self.assertEqual(entry.entry_start, 496)
        self.assertEqual(entry.id, 768)
        self.assertEqual(entry.name_idx, 10)
        self.assertEqual(entry.name, u'Gerwin ft. LaMeduza')

    def test_artist_page_with_strange_strings(self):
        file = open("tests/blobs/pdb_artists_strange_string.bin", "rb")
        parsed = AlignedPage.parse_stream(file)

        self.assertEqual(parsed.index, 725)
        self.assertEqual(parsed.page_type, "block_artists")
        self.assertEqual(parsed.entry_count_small, 4)
        self.assertEqual(parsed.entry_count, 4)
        self.assertEqual(len(parsed.entry_list), 1)
        self.assertEqual(parsed.entry_list[0].entry_count, 4)
        self.assertEqual(len(parsed.entry_list[0].entries), 4)

        long_entry = parsed.entry_list[0].entries[0]
        self.assertEqual(long_entry.entry_start, 184)
        self.assertEqual(long_entry.id, 1446)
        self.assertEqual(long_entry.name_idx, 12)
        self.assertEqual(long_entry.name, u'Nasri Atweh/Louis Bell/Hiten Bharadia/Mark Bradford/Frank Buelles/Clifton Dillon/Ryan Dillon/Björn Djupström/Sly Dunbar/Nathan')
