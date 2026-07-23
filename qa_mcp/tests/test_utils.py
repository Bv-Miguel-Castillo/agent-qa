from mcp_agente_qa.utils import clean_html, parse_steps_xml


def test_clean_html() -> None:
    raw = "<p>Hola <b>mundo</b></p><p>Linea 2</p>"
    cleaned = clean_html(raw)
    assert "Hola mundo" in cleaned
    assert "Linea 2" in cleaned


def test_parse_steps_xml() -> None:
    xml = (
        "<steps>"
        "<step><parameterizedString>Accion A</parameterizedString>"
        "<parameterizedString>Resultado A</parameterizedString></step>"
        "</steps>"
    )
    parsed = parse_steps_xml(xml)
    assert parsed["Actions"] == ["Accion A"]
    assert parsed["Expected"] == ["Resultado A"]
