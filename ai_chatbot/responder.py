from nlp_module import NLPProcessor
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch

class Responder:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.last_responses = []
        self.nlp = NLPProcessor()
        self.conversation_history = []  # To store recent messages for context
        self.max_history = 5  # Number of previous messages to keep for context

        # Load GPT-2 model and tokenizer for generative responses
        self.tokenizer = GPT2Tokenizer.from_pretrained("./fine_tuned_gpt2")
        self.model = GPT2LMHeadModel.from_pretrained("./fine_tuned_gpt2")
        self.model.eval()
        if torch.cuda.is_available():
            self.model.to('cuda')

    def generate_gpt2_response(self, prompt, max_new_tokens=50):
        import re
        inputs = self.tokenizer.encode(prompt, return_tensors="pt")
        attention_mask = torch.ones(inputs.shape, dtype=torch.long)
        if torch.cuda.is_available():
            inputs = inputs.to('cuda')
            attention_mask = attention_mask.to('cuda')
        outputs = self.model.generate(
            inputs,
            attention_mask=attention_mask,
            max_new_tokens=max_new_tokens,
            num_return_sequences=1,
            no_repeat_ngram_size=2,
            pad_token_id=self.tokenizer.eos_token_id,
            do_sample=True,
            top_k=50,
            top_p=0.95,
            temperature=0.7,
            eos_token_id=self.tokenizer.eos_token_id,
            bad_words_ids=[[self.tokenizer.unk_token_id], [self.tokenizer.bos_token_id]],
            early_stopping=False,
            num_beams=1,
            prefix_allowed_tokens_fn=None
        )
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Remove the prompt from the response
        response = response[len(prompt):].strip()
        # Clean unwanted tokens like [MEUDIX] or similar bracketed tags
        response = re.sub(r"\[[^\]]*\]", "", response)
        response = response.strip()
        return response

    def generate_response(self, message):
        self.conversation_history.append(message)
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)

        context_message = " ".join(self.conversation_history)
        doc = self.nlp.process(context_message)
        intent = self.nlp.get_intent(doc)
        entities = self.nlp.get_entities(doc)

        # INTENT-BASED HANDLING
        if intent == "greet":
            return "Hello!"
        elif intent == "bye":
            return "Goodbye! Have a great day."

        # NLP semantic similarity
        best_response = None
        best_score = 0
        for question, response in self.kb.pairs:
            question_doc = self.nlp.process(question)
            score = self.nlp.similarity(doc, question_doc)
            if score > best_score and score > 0.7:
                best_score = score
                best_response = response

        if not best_response:
            best_response = self.kb.find_response(message)

        if best_response and best_response not in self.last_responses:
            self.last_responses.append(best_response)
            if len(self.last_responses) > 20:
                self.last_responses.pop(0)
            # Add the new pair immediately to knowledge base for faster learning
            self.kb.add_pair(message, best_response)
            return best_response

        # If no good response found, generate with GPT-2
        gpt2_response = self.generate_gpt2_response(message)
        if gpt2_response:
            self.kb.add_pair(message, gpt2_response)
            return gpt2_response

        return "I'm not sure how to respond to that yet."
