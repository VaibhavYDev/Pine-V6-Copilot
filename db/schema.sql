create extension if not exists vector;

create table chunks (
    id           bigint generated always as identity primary key,
    source       text not null,
    heading      text not null,
    body         text not null,
    kind         text not null check (kind in ('note', 'script', 'signature')),
    symbols      text[] not null default '{}',
    search_text  text not null,
    fts          tsvector generated always as (to_tsvector('english', search_text)) stored,
    embedding    vector(768) not null,
    content_hash text not null unique
);

create index chunks_fts_idx on chunks using gin (fts);
create index chunks_symbols_idx on chunks using gin (symbols);

create table queries (
    id             uuid primary key default gen_random_uuid(),
    created_at     timestamptz not null default now(),
    question       text not null,
    variant        text not null,
    answer         text not null,
    code           text,
    findings       jsonb not null default '[]',
    attempts       int not null default 0,
    retrieved_ids  bigint[] not null default '{}',
    model          text not null,
    prompt_version text not null,
    input_tokens   int not null default 0,
    output_tokens  int not null default 0,
    latency_ms     int not null,
    helpful        boolean
);

create table daily_usage (
    day    date primary key,
    tokens bigint not null default 0,
    calls  int not null default 0
);
