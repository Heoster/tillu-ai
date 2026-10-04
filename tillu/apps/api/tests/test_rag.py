from app.rag import search_chunks

def test_local_retrieval_ranks_matching_passage():
    chunks=[{'content':'Gauss law relates electric flux to enclosed charge','page':1},{'content':'Organic chemistry reaction notes','page':2}]
    hits=search_chunks('electric flux Gauss',chunks)
    assert hits and hits[0]['page']==1
