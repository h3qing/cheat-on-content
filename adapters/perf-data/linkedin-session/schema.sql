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
