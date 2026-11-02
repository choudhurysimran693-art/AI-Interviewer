import './assessment-question.css';

/** Practice-style presentation using the assigned assessment's saved state and timer. */
export function AssessmentQuestion({kind,index,total,remaining,paused,question,category,snippet}:{kind:string;index:number;total:number;remaining:number;paused:boolean;question:string;category:string;snippet?:string}){
 const seconds=Math.max(0,Math.ceil(remaining));
 return <header className="assessment-question">
  <nav className="assessment-strip" aria-label="Question progress">{Array.from({length:total},(_,i)=><span key={i} className={i<index?'answered':i===index?'current':''} aria-current={i===index?'step':undefined} aria-label={`Question ${i+1}: ${i<index?'submitted':i===index?'current':'upcoming'}`}>{i+1}</span>)}</nav>
  <div className="assessment-meta"><strong>{kind==='aptitude'?'Aptitude / Reasoning Test':'Technical Assessment'}</strong><span>Question {index+1} of {total}</span><span className={'assessment-timer'+(seconds<15?' urgent':'')} role="timer" aria-label={paused?'Question timer paused':`${seconds} seconds remaining`}>{paused?'Paused':`${seconds}s remaining`}</span></div>
  <p className="assessment-format">MCQ · {category.replaceAll('_',' ')}</p>
  <h2 className="question-text">{question}</h2>
  {snippet&&<pre className="assessment-snippet">{snippet}</pre>}
  <p className="assessment-help">Choose your answer below. Each question submits automatically when its time expires.</p>
 </header>;
}
