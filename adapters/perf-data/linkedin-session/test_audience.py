"""受众分类（per-person）单测：classify_row 规则 + Connections.csv 解析 + 行映射。

纯函数、合成样本，不碰网络/库。跑：python test_audience.py
"""
from audience_members import parse_connections_csv, profile_key_from_url
from classify import classify_row
from sink_supabase import build_member_row


# ---- profile_key_from_url ----

def test_profile_key_from_url():
    assert profile_key_from_url("https://www.linkedin.com/in/johndoe/") == "johndoe"
    assert profile_key_from_url("https://www.linkedin.com/in/jane-smith-123?trk=x") == "jane-smith-123"
    assert profile_key_from_url("http://linkedin.com/in/abc") == "abc"
    assert profile_key_from_url("") is None
    assert profile_key_from_url("https://example.com/foo") is None


# ---- classify_row 规则 ----

def test_classify_student():
    assert classify_row("Computer Science Student at UC Berkeley") == "student"
    assert classify_row("MBA Candidate | Class of 2027") == "student"
    assert classify_row("Aspiring Data Scientist") == "student"
    assert classify_row("Software Engineering Intern") == "student"


def test_classify_educator():
    assert classify_row("Professor of Economics") == "educator"
    assert classify_row("Postdoctoral Researcher at MIT") == "educator"
    assert classify_row("Lecturer in Computer Science") == "educator"


def test_classify_recruiter():
    assert classify_row("Technical Recruiter at Google") == "recruiter_hr"
    assert classify_row("Talent Acquisition Partner") == "recruiter_hr"
    assert classify_row("Head of People Operations") == "recruiter_hr"


def test_classify_leadership():
    assert classify_row("Founder & CEO at Acme") == "leadership"
    assert classify_row("VP of Engineering") == "leadership"
    assert classify_row("Director of Product") == "leadership"
    assert classify_row("Co-Founder") == "leadership"


def test_classify_creator_media():
    assert classify_row("Content Creator & Podcaster") == "creator_media"
    assert classify_row("Tech Journalist") == "creator_media"
    assert classify_row("YouTuber | 100k subs") == "creator_media"


def test_classify_early_career():
    assert classify_row("Junior Frontend Developer") == "early_career"
    assert classify_row("Associate Consultant") == "early_career"


def test_classify_professional():
    assert classify_row("Software Engineer at Stripe") == "professional"
    assert classify_row("Senior Product Designer") == "professional"
    assert classify_row("Data Scientist") == "professional"


def test_classify_priority_student_beats_leadership():
    # "Student Body President" 是学生，不是 leadership
    assert classify_row("Student Body President") == "student"
    # 学生兼创始人 → 仍归学生（pre-career 信号优先）
    assert classify_row("CS Student | Aspiring Founder") == "student"


def test_classify_ambiguous_is_none():
    assert classify_row("") is None
    assert classify_row(None) is None
    assert classify_row("Open to work") is None
    assert classify_row("Helping people grow ✨") is None


# ---- Connections.csv 解析（含 LinkedIn 导出的 preamble）----

CSV_SAMPLE = (
    '"Notes:"\n'
    '"When exporting your connection data, you may notice ..."\n'
    "\n"
    "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
    "Jane,Doe,https://www.linkedin.com/in/jane-doe/,,Acme,Software Engineer,01 Jan 2024\n"
    "Bob,Lee,https://www.linkedin.com/in/boblee,,Berkeley,CS Student,15 Mar 2025\n"
    ",,,,,,\n"  # 脏行（无 URL）→ 跳过
)


def test_parse_connections_csv():
    rows = parse_connections_csv(CSV_SAMPLE)
    assert len(rows) == 2, rows
    r0 = rows[0]
    assert r0["profile_key"] == "jane-doe"
    assert r0["full_name"] == "Jane Doe"
    assert r0["headline"] == "Software Engineer"
    assert r0["company"] == "Acme"
    assert r0["relationship"] == "connection"
    assert r0["raw"]["connected_on"] == "01 Jan 2024"
    assert rows[1]["profile_key"] == "boblee"


def test_parse_connections_csv_empty():
    assert parse_connections_csv("garbage\nno header here") == []


# ---- 行映射（写库前的纯函数）----

def test_build_member_row():
    member = {
        "profile_key": "jane-doe",
        "full_name": "Jane Doe",
        "headline": "Software Engineer",
        "company": "Acme",
        "relationship": "connection",
        "raw": {"connected_on": "01 Jan 2024"},
    }
    row = build_member_row(member)
    # 只含 profile 列；category / classified_at 不在 upsert payload 里（避免覆盖已分类的行）
    assert row["profile_key"] == "jane-doe"
    assert row["full_name"] == "Jane Doe"
    assert row["relationship"] == "connection"
    assert "category" not in row
    assert "classified_at" not in row
    assert row["raw"]["connected_on"] == "01 Jan 2024"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"✓ {fn.__name__}")
    print(f"\n{len(fns)} passed")
