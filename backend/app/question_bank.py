"""Small reviewed starter bank. Keys and rubrics are never returned before submission."""
QUESTIONS = [
 ('technical','DSA','easy','Explain how a hash table finds a value and what happens when keys collide.',None,[],['Hash function maps a key to an index','Collisions use chaining or probing','Average lookup O(1), worst case O(n)']),
 ('technical','DSA','medium','Write pseudocode to detect a cycle in a singly linked list. Explain complexity.',None,[],['Slow and fast pointers advance at different speeds','A meeting indicates a cycle; null means no cycle','O(n) time and O(1) extra space']),
 ('technical','DSA','hard','Design an LRU cache with constant-time get and put. Explain eviction.',None,[],['Hash map finds cache entries','Doubly linked list tracks recency','Move accessed entries to front and evict tail','O(1) get and put']),
 ('technical','System design','easy','Why use a database index, and what trade-offs does it introduce?',None,[],['Index speeds up selected queries','Extra storage overhead','Writes must update indexes']),
 ('technical','System design','medium','Design a URL shortener. Describe storage, identifiers, and handling collisions.',None,[],['Store mapping from short key to URL','Generate unique identifiers and retry collisions','Cache frequent redirects','Validate inputs and rate limit']),
 ('technical','System design','hard','How would you keep an order service reliable when a payment service fails?',None,[],['Idempotency prevents duplicate payments','Timeout and bounded retry with backoff','Durable queue and reconciliation','Observe failures and track order state']),
 ('technical','Programming','easy','Explain the difference between a stack and a queue, with one use case each.',None,[],['Stack is last in first out','Queue is first in first out','Stack for undo; queue for job processing']),
 ('technical','Programming','medium','Explain how you would test a function that validates email addresses.',None,[],['Valid and invalid input examples','Boundary cases and empty values','Automated unit tests','Explicit validation requirements']),
 ('technical','Programming','hard','Two requests update the same bank balance concurrently. How do you prevent a lost update?',None,[],['Atomic transaction','Row lock or optimistic concurrency version','Retry conflicts','Avoid read-modify-write without synchronization']),
 ('aptitude','Quantitative','easy','A product costs 800. After a 15% discount, what is the price?','680',['680','685','700','720'],['15% of 800 is 120','800 minus 120 is 680']),
 ('aptitude','Quantitative','medium','A can finish a task in 12 days, B in 18 days. Working together, how many days do they need?','7.2',['6','7.2','9','15'],['Combined rate is 1/12 + 1/18 = 5/36','Time is 36/5 = 7.2 days']),
 ('aptitude','Quantitative','hard','A price increases by 20% then decreases by 20%. What is the net percentage change?','4% decrease',['No change','4% decrease','4% increase','8% decrease'],['Multiply original by 1.2 then 0.8','Final is 0.96 of original, a 4% decrease']),
 ('aptitude','Data interpretation','easy','Monthly sales were 20, 30, and 40 units. What was the average?','30',['25','30','35','40'],['Sum is 90','90 divided by 3 is 30']),
 ('aptitude','Data interpretation','medium','Revenue increased from 240 to 300. What is the percentage increase?','25%',['20%','25%','30%','60%'],['Increase is 60','60 / 240 × 100 = 25%']),
 ('aptitude','Data interpretation','hard','A team has 8 people averaging 70 points. Two people averaging 90 points join. What is the new average?','74',['72','74','76','80'],['Original total 560; new total 740','740 divided by 10 is 74']),
 ('aptitude','Numerical','easy','What is 3/4 of 120?','90',['60','80','90','100'],['Divide 120 by 4 then multiply by 3']),
 ('aptitude','Numerical','medium','A train travels 150 km in 2.5 hours. What is its average speed in km/h?','60',['50','60','65','75'],['Speed equals distance divided by time','150 / 2.5 = 60']),
 ('aptitude','Numerical','hard','A fair die is rolled twice. What is the probability the sum is 7?','1/6',['1/12','1/6','1/4','1/3'],['There are 36 equally likely outcomes','Six ordered pairs sum to 7']),
 ('reasoning','Logical','easy','All roses are flowers. Some flowers fade quickly. Must some roses fade quickly?','Cannot determine',['Yes','No roses fade','Cannot determine'],['The flowers that fade need not be roses']),
 ('reasoning','Logical','medium','If the server is down, the alert is on. The alert is off. What follows?','The server is not down',['The server is down','The server is not down','Nothing follows'],['Use the contrapositive of the implication']),
 ('reasoning','Logical','hard','Exactly one of A and B is true. If A is true, C is false. C is true. Which is true?','B',['A','B','Both A and B','Neither A nor B'],['C true rules out A','Exactly one true forces B']),
 ('reasoning','Verbal','easy','Choose the word closest in meaning to concise.','Brief',['Brief','Complex','Loud','Uncertain'],['Concise means brief and clear']),
 ('reasoning','Verbal','medium','A study finds people who exercise sleep better. Does this alone prove exercise causes better sleep?','No; correlation alone does not prove causation',['Yes','No; correlation alone does not prove causation','Sleep never affects exercise'],['Other variables and reverse causation may explain the association']),
 ('reasoning','Verbal','hard','A proposal says remote work improved productivity because output rose after the policy. What evidence best strengthens this claim?','Comparable teams without the policy did not improve',['Employees liked the policy','Comparable teams without the policy did not improve','The company changed its logo'],['A comparison group helps rule out a common external trend']),
 ('reasoning','Patterns','easy','Find the next number: 2, 4, 8, 16, …','32',['18','24','30','32'],['Each term doubles']),
 ('reasoning','Patterns','medium','Find the next number: 3, 6, 11, 18, …','27',['24','25','27','30'],['Differences are 3, 5, 7, then 9']),
 ('reasoning','Patterns','hard','Find the next number: 1, 2, 6, 24, 120, …','720',['240','600','720','840'],['Terms are factorials','Multiply by 6 for the next term']),
]

# Technical questions deliberately mix short MCQs with longer coding prompts.
# Option ids stay stable even when their display order is shuffled per session.
TECHNICAL_FORMATS = {
 'bank-001': {'question_type':'mcq_single','options_json':[{'id':'a','text':'Hash the key to an index, then resolve collisions with chaining or probing'},{'id':'b','text':'Scan every stored key from the beginning'},{'id':'c','text':'Sort the table before every lookup'},{'id':'d','text':'Store every value at index zero'}],'correct_option_ids':['a'],'option_explanations_json':{'a':'Correct: hashing chooses a bucket and a collision strategy handles duplicate buckets.','b':'A full scan describes a list, not normal hash-table lookup.','c':'Hash tables do not require sorting for lookup.','d':'Using one bucket removes the expected constant-time benefit.'},'shuffle_options':True,'negative_marking':False},
 'bank-002': {'question_type':'coding','accepts_pseudocode':True},
 'bank-003': {'question_type':'coding','accepts_pseudocode':True},
 'bank-004': {'question_type':'mcq_multi','options_json':[{'id':'a','text':'It can speed up reads that match the indexed columns'},{'id':'b','text':'It uses additional storage'},{'id':'c','text':'It can add work to inserts and updates'},{'id':'d','text':'It guarantees every query is constant time'}],'correct_option_ids':['a','b','c'],'option_explanations_json':{'a':'Correct: an index can avoid scanning every row.','b':'Correct: index structures consume disk and memory.','c':'Correct: writes must maintain affected indexes.','d':'Indexes help selected access paths but do not guarantee constant-time queries.'},'shuffle_options':True,'negative_marking':False},
 'bank-005': {'question_type':'coding','accepts_pseudocode':True},
 'bank-006': {'question_type':'coding','accepts_pseudocode':True},
 'bank-007': {'question_type':'true_false','question':'True or false: a stack removes the oldest inserted item first. Add a one-line justification.','options_json':[{'id':'true','text':'True'},{'id':'false','text':'False'}],'correct_option_ids':['false'],'option_explanations_json':{'true':'A stack is LIFO, so it removes the newest item first.','false':'Correct: FIFO describes a queue; a stack is LIFO.'},'shuffle_options':False,'negative_marking':False},
 'bank-008': {'question_type':'spot_bug','question':'Which issue makes this email validator accept an invalid address?','snippet_text':'def valid_email(value):\n    return "@" in value or "." in value','snippet_language':'python','options_json':[{'id':'a','text':'It uses OR instead of requiring both checks'},{'id':'b','text':'The function needs a loop'},{'id':'c','text':'The return type should be a string'},{'id':'d','text':'Python cannot search inside strings'}],'correct_option_ids':['a'],'option_explanations_json':{'a':'Correct: a value with only @ or only a dot is accepted.','b':'Membership checks do not require a loop in user code.','c':'A validator should return a boolean.','d':'The in operator supports string membership.'},'shuffle_options':True,'negative_marking':False},
 'bank-009': {'question_type':'code_output','question':'What does this code print?','snippet_text':'balance = 10\nfor amount in [3, 4]:\n    balance -= amount\nprint(balance)','snippet_language':'python','options_json':[{'id':'a','text':'3'},{'id':'b','text':'7'},{'id':'c','text':'4'},{'id':'d','text':'10'}],'correct_option_ids':['a'],'option_explanations_json':{'a':'Correct: 10 - 3 - 4 equals 3.','b':'This stops after only the first subtraction.','c':'This subtracts the wrong total.','d':'The loop changes balance twice.'},'shuffle_options':True,'negative_marking':False},
}

DSA_CHAPTERS=['Arrays & Strings','Linked Lists','Stacks & Queues','Trees','Graphs','Recursion & Backtracking','Sorting & Searching','Dynamic Programming','Hashing','Greedy Algorithms']
DSA_LADDER=[
 ('easy','mcq','Which operation is typically O(1) on an array when the index is known?',['Read an element by index','Insert at the beginning','Search an unsorted value','Resize the array'],'a',['Direct indexing uses the address plus an offset.']),
 ('medium','pseudocode','Write pseudocode to find the longest run of equal characters in a string.',[],None,['Scan once while tracking the current and best run.']),
 ('hard','code','Implement a two-pointer solution for a sorted two-sum array.',[],None,['Move the left or right pointer based on the sum.']),
]

def chapter_rows():
    rows=[]
    for chapter in DSA_CHAPTERS:
        for difficulty,kind,prompt,options,key,rubric in DSA_LADDER:
            rows.append({'id':f'dsa-{len(rows)+1:03}','category':'technical','subcategory':'DSA','chapter':chapter,'difficulty':difficulty,'question':prompt,'question_type':kind,'options_json':[{'id':chr(97+i),'text':v} for i,v in enumerate(options)],'correct_option_ids':[key] if key else [],'option_explanations_json':{},'accepts_pseudocode':kind=='pseudocode','shuffle_options':kind=='mcq','negative_marking':False,'snippet_text':'','snippet_language':'','key':options[0] if key=='a' and options else None,'options':options,'expected_points':rubric,'time_limit_seconds':75 if kind=='mcq' else 300})
    return rows

def seed_bank(db):
    import json
    from .db import PracticeQuestion
    from sqlalchemy import select
    existing={row.id:row for row in db.scalars(select(PracticeQuestion))}
    legacy_chapters={'bank-001':'Hashing','bank-002':'Linked Lists','bank-003':'Hashing'}
    for i,(track,topic,difficulty,text,key,options,rubric) in enumerate(QUESTIONS):
        qid=f'bank-{i+1:03}'
        option_rows=[{'id':chr(97+n),'text':value} for n,value in enumerate(options)]
        body={'category':track,'subcategory':topic,'chapter':legacy_chapters.get(qid,topic if track=='technical' else None),'difficulty':difficulty,'question':text,'key':key,
              'options':options,'options_json':option_rows,'correct_option_ids':([next((o['id'] for o in option_rows if o['text']==key), '')] if key else []),
              'option_explanations_json':{},'expected_points':rubric,'question_type':'mcq_single' if options else 'coding',
              'accepts_pseudocode':track=='technical' and not options,'shuffle_options':bool(options),'negative_marking':False,
              'snippet_text':'','snippet_language':'','time_limit_seconds':75 if options else (300 if track=='technical' else 90)}
        body.update(TECHNICAL_FORMATS.get(qid,{}))
        if body['question_type']!='coding':body['time_limit_seconds']=75
        body=json.loads(json.dumps(body))
        row=existing.get(qid)
        if row:
            if row.body!=body:row.body=body
        else: db.add(PracticeQuestion(id=qid,body=body))
    from .coding_bank import coding_rows
    from .practice_expansion import expanded_rows
    for body in [*chapter_rows(), *coding_rows(), *expanded_rows()]:
        body=json.loads(json.dumps(body))
        row=existing.get(body['id'])
        if row:
            if row.body!=body:row.body=body
        else: db.add(PracticeQuestion(id=body['id'],body=body))
    db.commit()
