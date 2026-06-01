"""법제처 Open API XML 파서 테스트."""

from tax_copilot.infra.law_open_data import LawOpenDataClient, build_law_chunks


def test_fetch_current_law_parses_article_documents() -> None:
    responses = {
        "lawSearch.do": """
        <LawSearch>
          <law>
            <법령일련번호>001</법령일련번호>
            <법령명한글>부가가치세법</법령명한글>
          </law>
        </LawSearch>
        """,
        "lawService.do": """
        <법령>
          <기본정보>
            <법령명_한글>부가가치세법</법령명_한글>
            <시행일자>20240101</시행일자>
          </기본정보>
          <조문>
            <조문단위>
              <조문번호>38</조문번호>
              <조문제목>공제하는 매입세액</조문제목>
              <조문내용>사업자가 자기의 사업을 위하여 공급받은 재화의 매입세액</조문내용>
            </조문단위>
          </조문>
        </법령>
        """,
    }

    client = LawOpenDataClient(
        api_key="test",
        fetch_text=lambda path, _params: responses[path],
    )

    documents = client.fetch_current_laws(["부가가치세법"])
    chunks = build_law_chunks(documents, corpus_version="test")

    assert len(chunks) == 1
    assert chunks[0].law_name == "부가가치세법"
    assert chunks[0].article_no == "제38조"
    assert "공제하는 매입세액" in chunks[0].content
    assert chunks[0].effective_from.isoformat() == "2024-01-01"


def test_fetch_nts_interpretations_uses_list_xml() -> None:
    xml = """
    <LawSearch>
      <item>
        <ID>NTS-1</ID>
        <안건명>매입세액 공제 여부</안건명>
        <생산일자>20240510</생산일자>
        <내용>전자세금계산서 수취분의 매입세액 공제에 관한 해석</내용>
      </item>
    </LawSearch>
    """
    client = LawOpenDataClient(api_key="test", fetch_text=lambda _path, _params: xml)

    documents = client.fetch_nts_interpretations(["세금계산서"])
    chunks = build_law_chunks(documents, corpus_version="test")

    assert len(chunks) == 1
    assert chunks[0].law_id == "nts-interpretation"
    assert chunks[0].law_name == "매입세액 공제 여부"
    assert "전자세금계산서" in chunks[0].content


def test_fetch_tax_tribunal_cases_fetches_body_xml() -> None:
    def fetch_text(path: str, _params: dict[str, str | int]) -> str:
        if path == "lawSearch.do":
            return """
            <LawSearch>
              <item>
                <ID>TT-1</ID>
                <사건명>부가가치세 부과처분 취소</사건명>
                <결정일자>20240315</결정일자>
              </item>
            </LawSearch>
            """
        return """
        <판례>
          <주문>처분청의 부가가치세 부과처분을 취소한다.</주문>
          <이유>세금계산서 수취 사실이 확인된다.</이유>
        </판례>
        """

    client = LawOpenDataClient(api_key="test", fetch_text=fetch_text)

    documents = client.fetch_tax_tribunal_cases(["부가가치세"])
    chunks = build_law_chunks(documents, corpus_version="test")

    assert len(chunks) == 1
    assert chunks[0].law_id == "tax-tribunal"
    assert chunks[0].law_name == "부가가치세 부과처분 취소"
    assert "부과처분을 취소" in chunks[0].content


def test_tax_tribunal_list_field_names_and_source_url_redaction() -> None:
    def fetch_text(path: str, _params: dict[str, str | int]) -> str:
        if path == "lawSearch.do":
            return """
            <Decc>
              <decc>
                <특별행정심판재결례일련번호>2084325</특별행정심판재결례일련번호>
                <사건명></사건명>
                <청구번호>조심 2025지1899</청구번호>
                <의결일자>2026.02.04</의결일자>
                <행정심판재결례상세링크>/DRF/lawService.do?OC=secret&amp;target=ttSpecialDecc</행정심판재결례상세링크>
              </decc>
            </Decc>
            """
        return "<판례><이유>취득세 부과처분에 관한 판단</이유></판례>"

    client = LawOpenDataClient(api_key="secret", fetch_text=fetch_text)

    documents = client.fetch_tax_tribunal_cases([""])
    chunks = build_law_chunks(documents, corpus_version="test")

    assert chunks[0].law_name == "조심 2025지1899"
    assert "OC=secret" not in chunks[0].source_url
    assert "OC=secret" not in chunks[0].content
