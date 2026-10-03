"""Hierarchical local RAG for large PDFs.

Indexing preserves page boundaries, creates overlapping semantic-sized chunks and attaches
lightweight section context. Retrieval combines term frequency, inverse document frequency,
phrase overlap and page diversity. A pgvector adapter can replace scoring without changing
API contracts.
"""
import re,math
from collections import Counter,defaultdict
from pypdf import PdfReader

WORD=re.compile(r"[a-z0-9][a-z0-9_-]+",re.I)
def normalize(text):return re.sub(r"\s+"," ",text or "").strip()
def tokens(text):return WORD.findall(text.lower())
def sentences(text):return re.split(r"(?<=[.!?])\s+",normalize(text))

def extract_chunks(path:str,chunk_chars:int=1800,overlap_chars:int=240,max_pages:int=500,max_chars:int=2_000_000):
    reader=PdfReader(path)
    if reader.is_encrypted:raise ValueError('Encrypted PDF')
    if len(reader.pages)>max_pages:raise ValueError('PDF exceeds page limit')
    chunks=[];last_heading="";total_chars=0
    for page_no,page in enumerate(reader.pages,1):
        raw=page.extract_text() or "";lines=[normalize(x) for x in raw.splitlines() if normalize(x)]
        for line in lines[:12]:
            if 4<=len(line)<=120 and (line.isupper() or len(line.split())<=9) and not line.endswith('.'):
                last_heading=line;break
        text=normalize(raw);total_chars+=len(text)
        if total_chars>max_chars:raise ValueError('PDF extracted text exceeds safety limit')
        if not text:continue
        parts=sentences(text);buffer=""
        for sentence in parts:
            candidate=(buffer+" "+sentence).strip()
            if len(candidate)>chunk_chars and buffer:
                chunks.append({"page":page_no,"content":(f"Section: {last_heading}\n" if last_heading else "")+buffer})
                buffer=buffer[-overlap_chars:]+" "+sentence
            else:buffer=candidate
        if buffer:chunks.append({"page":page_no,"content":(f"Section: {last_heading}\n" if last_heading else "")+buffer})
    return chunks

def search_chunks(query:str,chunks:list[dict],limit=6):
    if not chunks:return []
    q_tokens=tokens(query);q=Counter(q_tokens);docs=[Counter(tokens(c['content'])) for c in chunks];n=len(docs)
    df=Counter(t for d in docs for t in d);phrase=" ".join(q_tokens)
    ranked=[]
    for c,words in zip(chunks,docs):
        length=max(sum(words.values()),1);score=0.0
        for term,qw in q.items():
            tf=words[term];idf=math.log((n+1)/(df[term]+0.5))+1
            score+=qw*idf*(tf*(1.5+1))/(tf+1.5*(0.25+0.75*length/220)) if tf else 0
        content_lower=c['content'].lower()
        if phrase and phrase in content_lower:score+=4
        score+=sum(0.25 for a,b in zip(q_tokens,q_tokens[1:]) if f"{a} {b}" in content_lower)
        if score:ranked.append((score,c))
    ranked.sort(key=lambda x:x[0],reverse=True)
    selected=[];per_page=defaultdict(int)
    for score,c in ranked:
        if per_page[c['page']]>=2 and len(selected)<max(3,limit//2):continue
        selected.append(dict(c,score=round(score,3)));per_page[c['page']]+=1
        if len(selected)>=limit:break
    return selected
