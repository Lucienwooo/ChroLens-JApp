import re

def _parse_avwiki_title_tag(title_text, ccode_upper):
    found_actress = "未知"
    found_jp_title = None
    # Extract actress name: text immediately before 'に出てるAV女優は誰？'
    m_actress = re.search(r'([^\s。！？、。\.]+)に出てるAV女優は誰？', title_text)
    if m_actress:
        candidate = m_actress.group(1).strip()
        candidate = re.sub(r'^[「」【】（）\(\)\[\]。、！？\s]+', '', candidate).strip()
        if candidate:
            found_actress = candidate
    # Extract Japanese title: between '{CODE}：' and '{actress}に出てるAV女優は誰？'
    if found_actress != "未知":
        m_title = re.search(rf'{re.escape(ccode_upper)}：(.+?)\s*{re.escape(found_actress)}に出てるAV女優は誰？', title_text)
        if m_title:
            found_jp_title = m_title.group(1).strip()
        else:
            m_title2 = re.search(rf'：(.+?)\s*{re.escape(found_actress)}に', title_text)
            if m_title2:
                found_jp_title = m_title2.group(1).strip()
    return found_actress, found_jp_title

title = "MASM-017：愛おしすぎて壊しちゃいたい カワボなヤンデレJ系に監禁された俺の極限中出し搾精生活 胡桃さくらに出てるAV女優は誰？ 名前は？ | AV女優の名前が知りたい！ 本館"
actress, jp_title = _parse_avwiki_title_tag(title, "MASM-017")
print(f"actress: {actress}")
print(f"jp_title: {jp_title}")
