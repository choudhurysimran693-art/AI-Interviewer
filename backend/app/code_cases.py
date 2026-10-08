"""Server-owned input/output contracts. Only the first example is public."""
def cases(*pairs):
    return [{'input':i,'expected':o} for i,o in pairs]

SUITES = {
 '00-easy': ('Input: an integer array. Output: maximum or null.', cases(([3,1,9],9),([],None),([-8,-2,-5],-2),([4],4),([0,0],0))),
 '00-medium': ('Input: a string. Output: longest unique-substring length.', cases(('abcabcbb',3),('',0),('bbbb',1),('abba',2),('pwwkew',3))),
 '00-hard': ('Input: {s, target}. Output: minimum covering substring; choose the earliest on a tie.', cases(({'s':'ADOBECODEBANC','target':'ABC'},'BANC'),({'s':'a','target':'aa'},''),({'s':'aa','target':'aa'},'aa'),({'s':'','target':'a'},''),({'s':'abc','target':''},''))),
 '01-easy': ('Input/output: list values in traversal order. Build nodes internally if needed.', cases(([1,2,3],[3,2,1]),([],[]),([7],[7]),([1,1],[1,1]))),
 '01-medium': ('Input: {values, pos}, where pos is the zero-based tail cycle link, or -1. Output: cycle entry index or -1.', cases(({'values':[3,2,0,-4],'pos':1},1),({'values':[],'pos':-1},-1),({'values':[1],'pos':0},0),({'values':[1,2],'pos':-1},-1))),
 '01-hard': ('Input: arrays representing sorted lists. Output: merged sorted values.', cases(([[1,4],[2,3]],[1,2,3,4]),([],[]),([[],[0],[]],[0]),([[-2,1],[-2,3]],[-2,-2,1,3]))),
 '02-easy': ('Input: bracket string. Output: boolean.', cases(('([])',True),('',True),('([)]',False),(']',False),('(((',False))),
 '02-medium': ('Input: operations [enqueue,value], [dequeue], [empty]. Output: one result per operation; enqueue and empty dequeue return null.', cases(([['enqueue',1],['enqueue',2],['dequeue'],['empty']],[None,None,1,False]),([['empty'],['dequeue']],[True,None]),([['enqueue',3],['dequeue'],['enqueue',4],['dequeue'],['empty']],[None,3,None,4,True]))),
 '02-hard': ('Input: histogram heights. Output: maximum area.', cases(([2,1,5,6,2,3],10),([],0),([2,2],4),([1,2,3,4],6),([0],0))),
 '03-easy': ('Input: binary tree as [value,left,right], or null. Output: depth.', cases(([1,[2,None,None],None],2),(None,0),([4,None,None],1),([1,[2,[3,None,None],None],None],3))),
 '03-medium': ('Input: binary tree as [value,left,right], or null. Output: BST validity.', cases(([2,[1,None,None],[3,None,None]],True),(None,True),([2,[2,None,None],None],False),([5,[2,None,[6,None,None]],None],False))),
 '03-hard': ('Input: tree [value,left,right] or null. Implement serialize/deserialize internally and return the reconstructed tree. Functional round-trip tests do not prove serialization design.', cases(([1,None,[2,None,None]],[1,None,[2,None,None]]),(None,None),([-1,[0,None,None],None],[-1,[0,None,None],None]))),
 '04-easy': ('Input: {n, edges}; vertices 0..n-1. Output: component count.', cases(({'n':4,'edges':[[0,1],[2,3]]},2),({'n':0,'edges':[]},0),({'n':3,'edges':[]},3),({'n':3,'edges':[[0,1],[1,2],[2,0]]},1))),
 '04-medium': ('Input: {n, edges, source}, undirected edges. Output: distances in vertex order.', cases(({'n':4,'edges':[[0,1],[1,2]],'source':0},[0,1,2,-1]),({'n':1,'edges':[],'source':0},[0]),({'n':3,'edges':[[0,1],[0,2]],'source':2},[1,2,0]))),
 '04-hard': ('Input: {n, edges, source}; directed edges [from,to,weight]. Output: distances, -1 if unreachable.', cases(({'n':3,'edges':[[0,1,5],[0,2,1],[2,1,1]],'source':0},[0,2,1]),({'n':2,'edges':[],'source':0},[0,-1]),({'n':2,'edges':[[0,1,0]],'source':0},[0,0]))),
 '05-easy': ('Input: distinct integer array. Output: all subsets, each sorted; sort the outer array lexicographically.', cases(([1,2],[[],[1],[1,2],[2]]),([],[[]]),([3],[[],[3]]))),
 '05-medium': ('Input: integer array. Output: unique permutations sorted lexicographically.', cases(([1,1,2],[[1,1,2],[1,2,1],[2,1,1]]),([],[[]]),([2,2],[[2,2]]))),
 '05-hard': ('Input: positive n. Output: sorted arrangements, each an array of zero-based queen columns in row order.', cases((4,[[1,3,0,2],[2,0,3,1]]),(1,[[0]]),(2,[]),(3,[]))),
 '06-easy': ('Input: {values,target}, values sorted and distinct. Output: index or -1.', cases(({'values':[1,3,5],'target':3},1),({'values':[],'target':0},-1),({'values':[1],'target':1},0),({'values':[1,3],'target':2},-1))),
 '06-medium': ('Input: {values,target}. Output: [first,last].', cases(({'values':[1,2,2,3],'target':2},[1,2]),({'values':[],'target':1},[-1,-1]),({'values':[2,2,2],'target':2},[0,2]),({'values':[1,3],'target':2},[-1,-1]))),
 '06-hard': ('Input: [sortedArrayA,sortedArrayB]. Output: numeric median.', cases(([[1,3],[2]],2),(([1,2],[3,4]),2.5),(([],[4]),4),(([-3,-1],[0,2]),-0.5))),
 '07-easy': ('Input: nonnegative n. Output: number of stair paths.', cases((3,3),(0,1),(1,1),(10,89))),
 '07-medium': ('Input: {coins,amount}. Output: minimum coin count or -1.', cases(({'coins':[1,2,5],'amount':11},3),({'coins':[2],'amount':3},-1),({'coins':[2],'amount':0},0),({'coins':[],'amount':1},-1))),
 '07-hard': ('Input: [stringA,stringB]. Output: edit distance.', cases((['horse','ros'],3),(['','abc'],3),(['same','same'],0),(['kitten','sitting'],3))),
 '08-easy': ('Input: string. Output: first unique character or null.', cases(('leetcode','l'),('',None),('aabb',None),('aab','b'))),
 '08-medium': ('Input: string array. Output: groups with each group sorted and outer groups sorted lexicographically.', cases((['eat','tea','bat'],[['bat'],['eat','tea']]),([],[]),(['',''],[['','']]),(['a','b','a'],[['a','a'],['b']]))),
 '08-hard': ('Input: {capacity,ops}; ops [put,key,value] or [get,key]. Output: one result per op; put/missing get return null.', cases(({'capacity':1,'ops':[['put','a',1],['put','b',2],['get','a'],['get','b']]},[None,None,None,2]),({'capacity':0,'ops':[['put','a',1],['get','a']]},[None,None]),({'capacity':2,'ops':[['put','a',1],['put','b',2],['get','a'],['put','c',3],['get','b']]},[None,None,1,None,None]))),
 '09-easy': ('Input: intervals [start,end], with start < end. Output: maximum count.', cases(([[1,2],[2,3],[1,3]],2),([],0),([[0,5],[1,2],[2,3],[3,4]],3))),
 '09-medium': ('Input: nonnegative jump lengths. Output: minimum jumps or -1; empty input returns 0.', cases(([2,3,1,1,4],2),([0],0),([0,1],-1),([],0),([1,1,1],2))),
 '09-hard': ('Input: {target,fuel,stations}; stations [position,fuel]. Output: stops or -1.', cases(({'target':100,'fuel':10,'stations':[[10,60],[20,30],[30,30],[60,40]]},2),({'target':1,'fuel':1,'stations':[]},0),({'target':10,'fuel':1,'stations':[]},-1))),
 '10-easy': ('Input: ASCII text; words are runs of letters A-Z/a-z. Output: lowercase frequency object.', cases(('Hello, hello world!',{'hello':2,'world':1}),('',{}),('one-two ONE',{'one':2,'two':1}))),
 '10-medium': ('Input: nested integer arrays. Consume your iterator and return its flattened values. Tests check output, not laziness.', cases(([1,[2,[],[3]]],[1,2,3]),([],[]),([[[],[]]],[]))),
 '10-hard': ('Input: {capacity,ops}; ops [put,value] or [get]. Simulate a bounded queue; full put returns false, accepted put true, empty get null. These functional tests do not assess concurrency.', cases(({'capacity':1,'ops':[['put',1],['put',2],['get'],['get']]},[True,False,1,None]),({'capacity':2,'ops':[['put',1],['put',2],['get'],['get']]},[True,True,1,2]))),
 '11-easy': ('Input: ops [put,key,value], [get,key], [delete,key]. Output: one value per op; put/delete/missing get return null.', cases(([['put','x',1],['get','x'],['delete','x'],['get','x']],[None,1,None,None]),([['get','x']],[None]),([['put','x',1],['put','x',2],['get','x']],[None,None,2]))),
 '11-medium': ('Input: ops [put,time,key,value,ttl] or [get,time,key]. Output: one value per op; put/missing/expired get return null. Expiry is inclusive.', cases(([['put',0,'a',1,2],['get',1,'a'],['get',2,'a']],[None,1,None]),([['put',0,'a',1,0],['get',0,'a']],[None,None]),([['put',0,'a',1,1],['put',1,'a',2,3],['get',2,'a']],[None,None,2]))),
 '11-hard': ('Input: {capacity,rate,requests}; requests [time,client], consume one token each. Buckets start full; output acceptance booleans.', cases(({'capacity':2,'rate':1,'requests':[[0,'a'],[0,'a'],[0,'a'],[1,'a']]},[True,True,False,True]),({'capacity':1,'rate':0,'requests':[[0,'a'],[0,'b'],[1,'a']]},[True,True,False]))),
}

def execution_metadata(qid):
    key=qid.removeprefix('coding-v1-')
    if key not in SUITES:return {}
    contract,tests=SUITES[key]
    return {'execution_contract':contract+' Implement solve(data) and return the output as a JSON-compatible value.',
            'sample_tests':tests[:1], 'hidden_tests':tests[1:], 'supported_languages':['python','javascript'],
            'starter_code':{'python':'def solve(data):\n    # Return the result\n    return None\n',
                            'javascript':'function solve(data) {\n  // Return the result\n  return null;\n}\n'}}
