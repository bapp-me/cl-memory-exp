"""One real native database task per model before calibration."""
import json
from core import ROOT,Database,DB_TOOLS,run_pi,save

def main():
    db=Database()
    checks=[]
    for i in [0,19,20,39]:
        db.start(i)
        value=db._conn.execute(db.row['sql']).fetchone()[0]
        matched=db._evaluate_answer(str(value),db.row)
        wrong=db.tool('ANSWER',{'answer':'invalid'})
        checks.append({'index':i,'reference_matches':matched,'wrong_rejected':not db.score()['correct'],'safe_feedback':wrong})
    save(ROOT/'records/database-canary-checks.json',checks)
    assert all(x['reference_matches'] and x['wrong_rejected'] for x in checks)
    for model in ['deepseek','glm']:
        folder=ROOT/'runs'/('canary-database-'+model)
        if (folder/'execution.json').exists():continue
        db.start(0)
        episode,record=run_pi(model,db.prompt(),[],'no_memory',db,DB_TOOLS,folder)
        save(folder/'score.json',db.score())
        print(json.dumps({'model':model,**record,**db.score()}),flush=True)

if __name__=='__main__':main()
