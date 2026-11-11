with q as (
    select (
        select string_agg(quote_literal(lexeme), ' | ')
        from unnest(to_tsvector('english', %(question)s))
    )::tsquery as terms
),
by_text as (
    select c.id, row_number() over (order by ts_rank_cd(c.fts, q.terms) desc, c.id) as rank
    from chunks c, q
    where c.fts @@ q.terms
    order by rank
    limit %(pool)s
),
by_vector as (
    select id, row_number() over (order by embedding <=> %(embedding)s::vector, id) as rank
    from chunks
    order by rank
    limit %(pool)s
)
select c.id, c.source, c.heading, c.body, c.kind, c.symbols,
       coalesce(1.0 / (60 + t.rank), 0) + coalesce(1.0 / (60 + v.rank), 0) as score
from by_text t
full outer join by_vector v using (id)
join chunks c using (id)
order by score desc, c.id
limit %(k)s;
