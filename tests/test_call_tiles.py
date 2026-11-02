"""Call grids: the real tiles of a group-call screen, found from its dark gutters (no model call)."""

from PIL import Image


def test_a_call_grid_is_found_from_its_gutters_and_nothing_else_is():
    from PIL import ImageDraw

    from whynot.assets.cutouts import call_tiles

    img = Image.new("RGB", (900, 2000), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for r in range(3):  # 3 rows x 2 columns of bright "videos", 6 px dark gutters, a thin controls bar below
        for c in range(2):
            d.rectangle((c * 453, r * 506, c * 453 + 446, r * 506 + 499), fill=(180, 140 + 20 * r, 120))
    d.rectangle((300, 300, 340, 340), fill=(0, 0, 0))  # a dark patch inside a video never splits its tile
    d.rectangle((40, 1700, 860, 1800), fill=(90, 90, 90))  # the call buttons: too thin to be a row of videos
    tiles = call_tiles(img)
    assert len(tiles) == 6 and tiles[0][:2] == (0, 0) and all(y1 <= 1520 for _, _, _, y1 in tiles)
    assert call_tiles(Image.new("RGB", (900, 2000), (240, 240, 240))) == []  # a chat screen: no grid
