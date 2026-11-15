Where can vectors be stored?
Options include:
- Redis with the Redis Query Engine/vector-search capabilities available in your Redis deployment.
- PostgreSQL with pgvector.
- Dedicated vector databases.

                    +-------------------------+
                    |      PostgreSQL         |  SOURCE OF TRUTH
                    | users, documents,       |  durable, transactional
                    | chunks, chat history    |
                    +-----------+-------------+
                                | derived from
              +-----------------+------------------+
              v                                    v
     +-----------------+                 +------------------+
     |     Qdrant      |                 |      Redis       |
     | vector index of |                 | fast, disposable |
     | document chunks |                 | layer            |
     +-----------------+                 +------------------+
        (rebuildable)                      cache, semantic cache,
                                           job queue, rate limits