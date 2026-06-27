-- audience_snapshots：受众分析快照（surface 3）。在 Supabase SQL Editor 里跑一次。
-- profile_stats / engagement_snapshots 用账号已有的表，不在这里建。

create table if not exists audience_snapshots (
  id               bigint generated always as identity primary key,
  captured_at      timestamptz not null default now(),
  total_followers  integer,
  top_demographics jsonb,   -- {seniority:{bucket,pct}, company_size:{...}, location, industry, job_title, company}
  raw              jsonb
);

-- 趋势查询示例：
--   select captured_at, total_followers,
--          top_demographics->'seniority'->>'bucket' as top_seniority
--   from audience_snapshots order by captured_at;


-- audience_members：逐人受众画像。一人一行，profile_key 唯一 → 可幂等 upsert，
-- 不必每次重爬。category 为空=还没分类（排队等 classify / LLM tail）。
create table if not exists audience_members (
  id             bigint generated always as identity primary key,
  profile_key    text unique not null,   -- /in/<slug> 的 slug，稳定去重键
  full_name      text,
  headline       text,                    -- = Connections.csv 的 Position（或 followers 卡片副标题）
  company        text,
  relationship   text,                    -- 'connection' | 'follower'
  category       text,                    -- student|early_career|professional|leadership|recruiter_hr|educator|creator_media|other
  classified_at  timestamptz,             -- null = 还没分类
  first_seen_at  timestamptz not null default now(),
  raw            jsonb
);

-- 受众构成查询示例：
--   select category, count(*) from audience_members group by category order by 2 desc;
--   select relationship, count(*) from audience_members group by relationship;
