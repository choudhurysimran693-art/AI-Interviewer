"""Additional deterministic practice exercises with checked answer keys."""
def expanded_rows():
    for level_index,level in enumerate(['easy','medium','hard']):
        for i in range(40):
            n=i+3
            if level=='easy':
                question=f'A shop sells {n} boxes with 12 pens each. How many pens are sold?';answer=n*12
            elif level=='medium':
                question=f'A product costs {n*100} rupees. After a 20% discount, what is its price?';answer=n*80
            else:
                question=f'{n} workers complete a job in 12 days. At equal productivity, how many days would {n*3} workers need for twice the work?';answer=8
                # A second varying quantity avoids identical solutions in every variant.
                days=6+i;question=f'{n} workers complete a job in {days} days. How many days do {n*2} equally productive workers need for four times that work?';answer=days*2
            yield row(f'expanded-aptitude-{level}-{i}','aptitude',level,question,answer)
            step=i+2
            if level=='easy':
                sequence=[n+j*step for j in range(4)];answer=n+4*step
                question=f'What comes next in this arithmetic sequence: {", ".join(map(str,sequence))}?'
            elif level=='medium':
                sequence=[n*(2**j) for j in range(4)];answer=n*16
                question=f'What comes next in this doubling sequence: {", ".join(map(str,sequence))}?'
            else:
                sequence=[n+j*j+step*j for j in range(4)];answer=n+16+step*4
                question=f'The differences increase by 2 each step. What comes next: {", ".join(map(str,sequence))}?'
            yield row(f'expanded-reasoning-{level}-{i}','reasoning',level,question,answer)

def row(qid,category,level,question,answer):
    values=[str(answer),str(answer+1),str(answer-1),str(answer+3)]
    return {'id':qid,'category':category,'subcategory':'Quantitative' if category=='aptitude' else 'Patterns','chapter':None,'difficulty':level,'question':question,'key':str(answer),'options':values,'options_json':[{'id':chr(97+i),'text':v} for i,v in enumerate(values)],'correct_option_ids':['a'],'option_explanations_json':{'a':f'The correct result is {answer}.'},'expected_points':[f'Result: {answer}','Explain each calculation'],'question_type':'mcq_single','accepts_pseudocode':False,'shuffle_options':True,'negative_marking':False,'snippet_text':'','snippet_language':'','time_limit_seconds':90}
