import requests

WHATSAPP_ACCESS_TOKEN = "EAAMsSi6HOiwBQfR7Yqt21qt3SAXNZCTNdKQ3ySbEeFTgh8F2BeUTjC3VGt5jDbsOruJ36Qd0YQ1GZAf69DTnEcN06n9ZCvZCTqR1rMZBmyTm5xY2rbzjsjVgZAIkv7a9foVPxPHXZAJqscy2BGOhxzsPypY7hgY3THGoJboAL99IDkJPWb8qJe4wWUNNegLOJPZBmPfB4fZCvgVgJqEBbmzr1ZBLdAEVGoTGiISjpZBN82tkVbxOivyoI37v6oMAvAXO9JV4rZB4rKdOvscZB7aA2GCsZChAC7"
PHONE_NUMBER_ID = "912660558596818"
API_VERSION = "v22.0"

BASE_URL = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"

HEADERS = {
    "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# -----------------------------
# FORMAT PHONE NUMBER
# -----------------------------
def format_phone(number):
    number = str(number).strip()
    if number.startswith("+"):
        return number
    if len(number) == 10 and number.isdigit():
        return "+91" + number
    return None


# -----------------------------
# SEND TEXT MESSAGE
# -----------------------------
def send_whatsapp_text(to, message):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    return requests.post(BASE_URL, headers=HEADERS, json=payload).json()


# -----------------------------
# SEND IMAGE
# -----------------------------
def send_whatsapp_image(to, image_url, caption=None):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url}
    }
    if caption:
        payload["image"]["caption"] = caption

    return requests.post(BASE_URL, headers=HEADERS, json=payload).json()


# -----------------------------
# SEND DOCUMENT (PDF)
# -----------------------------
def send_whatsapp_document(to, doc_url, filename="document.pdf"):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {
            "link": doc_url,
            "filename": filename
        }
    }
    return requests.post(BASE_URL, headers=HEADERS, json=payload).json()


def send_whatsapp_template(to, template_name, template_params=[]):
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en_US"},
            "components": [
                {
                    "type": "body",
                    "parameters": template_params
                }
            ]
        }
    }

    return requests.post(BASE_URL, headers=HEADERS, json=payload).json()
