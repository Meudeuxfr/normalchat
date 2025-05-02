import spacy

class NLPProcessor:
    def __init__(self):
        # Load the medium English model from spaCy with word vectors
        self.nlp = spacy.load("en_core_web_md")

    def process(self, text):
        return self.nlp(text)

    def get_intent(self, doc):
        # Placeholder for intent recognition logic
        # For now, just return the root verb or None
        for token in doc:
            if token.dep_ == "ROOT":
                return token.lemma_
        return None

    def get_entities(self, doc):
        return [(ent.text, ent.label_) for ent in doc.ents]

    def similarity(self, doc1, doc2):
        return doc1.similarity(doc2)
