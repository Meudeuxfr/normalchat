import spacy

class NLPProcessor:
    def __init__(self):
        # Load the medium English model from spaCy with word vectors
        self.nlp = spacy.load("en_core_web_md")

    def process(self, text):
        return self.nlp(text)

    def get_intent(self, doc):
        # Improved intent recognition using keyword matching with word boundaries
        import re
        text = doc.text.lower()
        greetings = ["hello", "hi", "hey", "greetings"]
        farewells = ["bye", "goodbye", "see you", "farewell"]

        for greet in greetings:
            if re.search(r'\\b' + re.escape(greet) + r'\\b', text):
                return "greet"
        for bye in farewells:
            if re.search(r'\\b' + re.escape(bye) + r'\\b', text):
                return "bye"
        return None

    def get_entities(self, doc):
        return [(ent.text, ent.label_) for ent in doc.ents]

    def similarity(self, doc1, doc2):
        return doc1.similarity(doc2)
