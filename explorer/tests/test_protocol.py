from tt_explorer import protocol


def test_parse_ok_with_payload():
    r = protocol.parse_reply("ok 1000000")
    assert r.ok and r.payload == "1000000"


def test_parse_ok_bare():
    r = protocol.parse_reply("ok")
    assert r.ok and r.payload == ""


def test_parse_err():
    r = protocol.parse_reply("err bad-design", ["# detail"])
    assert not r.ok
    assert r.payload == "bad-design"
    assert r.info == ["# detail"]


def test_reply_line_detection():
    assert protocol.is_reply_line("ok 42")
    assert protocol.is_reply_line("err mode")
    assert not protocol.is_reply_line("# info")
    assert protocol.is_info_line("# info")


def test_parse_hello():
    h = protocol.parse_hello("tt-explorer 2 shuttle=ttsky25b")
    assert h == {"version": 2, "shuttle": "ttsky25b"}


def test_parse_hello_ignores_unknown_fields():
    h = protocol.parse_hello("tt-explorer 3 shuttle=ttsky26a extra=1")
    assert h["version"] == 3
    assert h["shuttle"] == "ttsky26a"


def test_parse_status():
    st = protocol.parse_status(
        "design=448 mode=run freq=1000000 ui=0a uidrv=1 uiod=f0")
    assert st["design"] == 448
    assert st["mode"] == "run"
    assert st["freq"] == 1000000
    assert st["ui"] == 0x0A
    assert st["uidrv"] == 1
    assert st["uiod"] == 0xF0


def test_parse_status_unselected():
    st = protocol.parse_status(
        "design=-1 mode=step freq=1000000 ui=00 uiod=00")
    assert st["design"] == -1
    assert st["mode"] == "step"


def test_hex_byte_roundtrip():
    assert protocol.hex_byte(0) == "00"
    assert protocol.hex_byte(255) == "ff"
    assert protocol.parse_hex_byte("a5") == 0xA5


def test_seven_seg():
    from tt_explorer.widgets import seven_seg
    # 0x6d lights a..g for the digit 5: a,c,d,f,g on; b,e,dp off
    assert seven_seg(0x6D) == " _ \n|_ \n _| "
    assert seven_seg(0x00) == "   \n   \n    "
    assert seven_seg(0xFF) == " _ \n|_|\n|_|."


def test_parse_hz():
    from tt_explorer.app import parse_hz
    assert parse_hz("440") == 440
    assert parse_hz("32k") == 32_000
    assert parse_hz("1.5M") == 1_500_000
    assert parse_hz("200 kHz") == 200_000
    assert parse_hz("2m") == 2_000_000
    assert parse_hz("") is None
    assert parse_hz("fast") is None
    assert parse_hz("0") is None


def test_uio_direction_hint():
    from tt_explorer.widgets import UioPanel
    hint = UioPanel._dir_hint
    assert hint("dac_wr_OUT (active low)") == "out"
    assert hint("CONFIG ADDR_0_IN") == "in"
    assert hint("DATA_INPUT_3") == "in"
    assert hint("segment output g") == "out"
    assert hint("spi_cs") is None
    assert hint("") is None


def test_upy_translate():
    from tt_explorer.upy_link import UpyLink
    link = UpyLink.__new__(UpyLink)
    link._last_freq = 0
    assert link._translate("hello") == "_tt_hello()"
    assert link._translate("status") == "_tt_status()"
    assert link._translate("design 448") == "_tt_design(448)"
    assert "clock_project_PWM(1000)" in link._translate("freq 1000")
    assert link._last_freq == 1000
    assert "clock_project_PWM(1000)" in link._translate("resume")
    assert link._translate("step 10") == "_tt_step(10)"
    assert link._translate("ui ff") == "_tt_ui(255)"
    assert "ASIC_MANUAL_INPUTS" in link._translate("ui off")
    assert "uio_oe_pico.value = 240" in link._translate("uiod f0")
    assert link._translate("ui zz") is None
    assert link._translate("bogus") is None
