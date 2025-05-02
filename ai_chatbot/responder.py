from nlp_module import NLPProcessor

class Responder:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.last_responses = []
        self.nlp = NLPProcessor()
        self.conversation_history = []  # To store recent messages for context
        self.max_history = 5  # Number of previous messages to keep for context

    def generate_response(self, message):
        # Add the new message to conversation history
        self.conversation_history.append(message)
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)

        # Combine recent messages to form context
        context_message = " ".join(self.conversation_history)
        doc = self.nlp.process(context_message)
        intent = self.nlp.get_intent(doc)
        entities = self.nlp.get_entities(doc)

        # Use NLP semantic similarity to find best response based on context
        best_response = None
        best_score = 0
        for question, response in self.kb.pairs:
            question_doc = self.nlp.process(question)
            score = self.nlp.similarity(doc, question_doc)
            if score > best_score and score > 0.7:
                best_score = score
                best_response = response

        # Fallback to existing sequence matching if no good NLP match
        if not best_response:
            best_response = self.kb.find_response(message)

        # Avoid repetition by checking last responses
        if best_response and best_response not in self.last_responses:
            self.last_responses.append(best_response)
            if len(self.last_responses) > 20:
                self.last_responses.pop(0)
            return best_response

        # Default fallback response
        return "I'm not sure how to respond to that yet."
