from whynot.assets.sam import parse

SAMPLE = (
    "<|box;x1=12;y1=40;x2=300;y2=320;w=320;h=334;c=0.93|>"
    "<|mask;x=0;y=0;c=0.93;data=64,60,~abc:DEF+ghi|>"
    "<|box;x1=1;y1=2;x2=3;y2=4;w=320;h=334|>"
)


def test_parse_boxes_and_masks():
    boxes, masks = parse(SAMPLE)
    assert len(boxes) == 2 and len(masks) == 1
    assert (boxes[0].x1, boxes[0].y2, boxes[0].frame_w, boxes[0].confidence) == (12, 320, 320, 0.93)
    assert boxes[1].confidence is None
    assert (masks[0].height, masks[0].width, masks[0].encoding) == (64, 60, "~")
    assert masks[0].payload == "abc:DEF+ghi"


def test_parse_empty():
    assert parse("no matches here") == ([], [])
