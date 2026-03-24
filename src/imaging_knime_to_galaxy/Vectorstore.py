import numpy as np

class VectorStore:
    def __init__(self, embed_fn, texts=None, metadatas=None,
                 dtype=np.float32, normalize=True):
        self.embed_fn = embed_fn
        self.dtype = dtype
        self.normalize = normalize
        self.vectors = np.empty((0, 0), dtype=dtype)  # (n_docs, dim)
        self.texts = []
        self.metadatas = []
        if texts:
            self.add(texts, metadatas)

    def _prep_vec(self, v):
        a = np.asarray(v, dtype=self.dtype)
        if self.normalize:
            n = np.linalg.norm(a)
            if n > 0:
                a = a / n
        return a

    def add(self, texts, metadatas=None):
        if isinstance(texts, str):
            texts = [texts]
        if metadatas is None:
            metadatas = [None] * len(texts)
        embs = []
        for t in texts:
            e = self.embed_fn(t)
            if e is None:
                # überspringe leere Texte
                continue
            embs.append(self._prep_vec(e))
        if not embs:
            return
        M = np.vstack(embs)
        if self.vectors.size == 0:
            self.vectors = M
        else:
            if M.shape[1] != self.vectors.shape[1]:
                raise ValueError("All embeddings need to have the same shape.")
            self.vectors = np.vstack([self.vectors, M])
        self.texts.extend(texts[:len(embs)])
        self.metadatas.extend(metadatas[:len(embs)])

    def search(self, query, k=3, return_scores=False):
        if len(self.texts) == 0:
            return [] if not return_scores else []
        q = self._prep_vec(self.embed_fn(query))
        if self.vectors.size == 0:
            return [] if not return_scores else []
        sims = self.vectors @ q
        k = min(k, len(self.texts))
        idx = np.argpartition(-sims, k - 1)[:k]
        idx = idx[np.argsort(-sims[idx])]
        results = [
            {"text": self.texts[i], "meta": self.metadatas[i]}
            for i in idx
        ]
        if return_scores:
            return [(results[j], float(sims[idx[j]])) for j in range(len(idx))]
        return results

    def save(self, path):
        np.savez(
            path,
            vectors=self.vectors,
            texts=np.array(self.texts, dtype=object),
            metadatas=np.array(self.metadatas, dtype=object)
        )

    @classmethod
    def load(cls, path, embed_fn):
        data = np.load(path, allow_pickle=True)
        obj = cls(embed_fn=embed_fn)
        obj.vectors = data["vectors"]
        obj.texts = list(data["texts"])
        obj.metadatas = list(data["metadatas"])
        return obj