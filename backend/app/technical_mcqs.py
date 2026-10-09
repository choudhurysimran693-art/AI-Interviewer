"""General software fundamentals for the technical MCQ round (server-side keys)."""
ITEMS = [
    ('Which data structure removes the most recently inserted item first?', ['Queue', 'Stack', 'Set', 'Graph'], 'b', 'Data structures'),
    ('What is the worst-case time complexity of binary search on a sorted array?', ['O(n)', 'O(n log n)', 'O(log n)', 'O(n²)'], 'c', 'Algorithms'),
    ('Which traversal finds shortest paths by edge count in an unweighted graph?', ['Breadth-first search', 'Depth-first search', 'Inorder traversal', 'Selection sort'], 'a', 'Graphs'),
    ('What is the worst-case time complexity of merge sort?', ['O(n²)', 'O(log n)', 'O(1)', 'O(n log n)'], 'd', 'Sorting'),
    ('Which technique detects a cycle in a singly linked list using O(1) extra space?', ['Copying all nodes into an array', 'Slow and fast pointers', 'Sorting the nodes', 'Binary search'], 'b', 'Linked lists'),
    ('With a good hash function and a bounded load factor, what is expected hash-table lookup time?', ['O(1)', 'O(n²)', 'O(n log n)', 'O(n)'], 'a', 'Hashing'),
    ('What does transaction atomicity mean?', ['Every query runs in constant time', 'All users share one connection', 'All operations commit together or none do', 'Data is never updated'], 'c', 'Databases'),
    ('Which SQL clause filters groups after aggregation?', ['ORDER BY', 'WHERE', 'LIMIT', 'HAVING'], 'd', 'SQL'),
    ('Which constraint ensures a referenced row exists in another table?', ['DEFAULT', 'FOREIGN KEY', 'NOT NULL', 'CHECK for a positive number'], 'b', 'Databases'),
    ('What does HTTP status 404 normally indicate?', ['Successful creation', 'Authentication succeeded', 'The requested resource was not found', 'The server redirected the request'], 'c', 'HTTP'),
    ('Which approach prevents SQL injection when inserting user-supplied values into a query?', ['Parameterized queries', 'Concatenating raw input', 'Removing spaces from input', 'Hiding the query in the browser'], 'a', 'Security'),
    ('What is a race condition?', ['A program always finishes quickly', 'A loop has no exit condition', 'A compiler rejects invalid syntax', 'A result depends on the timing of concurrent operations'], 'd', 'Concurrency'),
    ('What is the primary purpose of a unit test?', ['Measure production network traffic', 'Check a small unit of behavior with controlled inputs', 'Replace all integration tests', 'Guarantee the absence of every bug'], 'b', 'Testing'),
    ('Which structure naturally supports processing jobs in first-in, first-out order?', ['Stack', 'Binary search tree', 'Queue', 'Unordered set'], 'c', 'Data structures'),
    ('For an idempotent operation, what happens when the same request is successfully applied repeatedly?', ['Its intended effect is the same as applying it once', 'It must return a different result every time', 'It cannot use a database', 'It must execute only in the browser'], 'a', 'APIs'),
]


def questions():
    return [{'question': prompt, 'difficulty': 'easy', 'subcategory': topic,
             'options_json': [{'id': chr(97+i), 'text': text} for i, text in enumerate(options)],
             'correct_option_ids': [key], 'time_limit_seconds': 90}
            for prompt, options, key, topic in ITEMS]
