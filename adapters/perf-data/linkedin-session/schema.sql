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


-- audience_composition：受众构成的时间序列快照（趋势用）。每次 snapshot 写一行，
-- 把当下 audience_members 的分类计数定格下来，好看「学生/年轻人占比」随接受请求而上升。
create table if not exists audience_composition (
  id           bigint generated always as identity primary key,
  captured_at  timestamptz not null default now(),
  total        integer,
  connections  integer,
  followers    integer,
  by_category  jsonb,   -- {student:80, professional:2247, ...}
  raw          jsonb
);

-- 趋势查询示例（年轻人占比随时间）：
--   select captured_at, total,
--          (by_category->>'student')::int + coalesce((by_category->>'early_career')::int,0) as young,
--          round(100.0*((by_category->>'student')::int + coalesce((by_category->>'early_career')::int,0))/total,1) as young_pct
--   from audience_composition order by captured_at;
