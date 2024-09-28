from flask import Flask, request, render_template, redirect, url_for, jsonify, session
from flask_mysqldb import MySQL
import pandas as pd
import nltk
import requests
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import time
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random
import string
import os
import whisper

app = Flask(__name__)

app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
model = whisper.load_model("base.en")
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')

data = pd.read_csv("BankFAQs.csv")
prompt_questions = data.head(100)["Question"].tolist()

stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

def preprocess_text(text):
    t=str(text)
    tokens = word_tokenize(t.lower()) 
    tokens = [token for token in tokens if token.isalnum() or token in stop_words]  
    tokens = [lemmatizer.lemmatize(token) for token in tokens]  
    return " ".join(tokens)

data['Question'] = data['Question'].apply(preprocess_text)

tfidf_vectorizer = TfidfVectorizer()
X = tfidf_vectorizer.fit_transform(data['Question'])
y = LabelEncoder().fit_transform(data['Class'])

rf_classifier = RandomForestClassifier(random_state=42)
rf_classifier.fit(X, y)

api_responses = {}

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'chatbot'

mysql = MySQL(app)

@app.route('/')
def index():
    return render_template('index.html')

def store_data(question,answer,email):
    data = request.json
    message = data.get('message')
    reply = data.get('reply')

    cursor = mysql.connection.cursor()
    query = "INSERT INTO chat_history (question, answer,user_email) VALUES (%s, %s, %s)"
    values = (question, answer, email)
    cursor.execute(query, values)
    mysql.connection.commit()

def fetch_answer_from_api(question):
    try:
        url = 'http://localhost:3001/ajax'
        headers = {'Content-Type': 'application/json'}
        data = {'question': question}

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            generated_content = response.json()['data']
        else:
            print("Failed to fetch generated content. Status code:", response.status_code)
    except Exception as e:
        print("Error:", e)
    return generated_content

def get_response(usr_text, data):
    cleaned_text = preprocess_text(usr_text)
    if cleaned_text in data['Question'].values:
        response = data[data['Question'] == cleaned_text]['Answer'].values[0]
        store_data(usr_text,response,session.get('user_id'))
        return response
    else:
        if cleaned_text in api_responses:
            store_data(usr_text,api_responses[cleaned_text],session.get('user_id'))
            return api_responses[cleaned_text]
        else:
            api_response = fetch_answer_from_api(usr_text)
            if api_response:
                new_row = {'Question': cleaned_text, 'Answer': api_response,'Class':'websearch'}
                data = pd.concat([data, pd.DataFrame([new_row])], ignore_index=True)
                data.to_csv("BankFAQs.csv", index=False)
                api_responses[cleaned_text] = api_response
                store_data(usr_text,api_response,session.get('user_id'))
                return api_response
            else:
                response="I'm sorry, I don't have an answer to that question."
                store_data(usr_text,response,session.get('user_id'))
                return response

@app.route('/send_history', methods=['POST'])
def send_history():
    sender_email = "nilesh1718@outlook.com"
    receiver_email = session.get('user_id')
    password = "Nilesh@cs046"
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("SELECT time, question, answer FROM chat_history WHERE user_email=%s", (receiver_email,))
    chat_history = cursor.fetchall()

    body = "Chat History:\n\n"
    for item in chat_history:
        date = item[0]
        question = item[1]
        answer = item[2]
        body += f"Date: {date}\nQuestion: {question}\nAnswer: {answer}\n\n"

    msg = MIMEMultipart('alternative')
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "Chat History"

    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP('smtp.office365.com', 587)
    server.starttls()
    server.login(sender_email, password)
    server.sendmail(sender_email, receiver_email, msg.as_string())
    server.quit()

    return jsonify({'success': True,'message': 'Email sent successfully!'})

@app.route('/sendotp', methods=['POST'])
def sendotp():
    try:
        email_to_check = request.form['email']
    except KeyError:
        return jsonify({'success': False, 'message': 'Invalid form data'})
    cursor = mysql.connection.cursor()
    query = "SELECT * FROM users WHERE email = %s"
    cursor.execute(query, (email_to_check,))
    user = cursor.fetchone()
    cursor.close()
    if user:
        characters = string.ascii_letters + string.digits
        otp = ''.join(random.choice(characters) for _ in range(8))
        email = email_to_check
        new_password = otp
        cur = mysql.connection.cursor()
        update_query = "UPDATE users SET password = %s, password_reset = %s WHERE email = %s"
        cur.execute(update_query, (new_password,1, email))
        mysql.connection.commit()
        cur.close()
        cursor = mysql.connection.cursor()
        query = "SELECT name FROM users WHERE email = %s"
        cursor.execute(query, (email_to_check,))
        name = cursor.fetchone()
        cursor.close()
        
        sender_email = "nilesh1718@outlook.com"
        receiver_email = email_to_check
        password = "Nilesh@cs046"

        body = f"""
        Dear {name[0]}, 
        
        
        We hope this email finds you well.

        Your password reset request has been successfully processed. Your new password is {otp}

        Please follow the steps below to reset your password:

        1. Log in to your account using your existing username and the temporary password provided in this email.
        2. Once logged in, navigate to the Password Reset section.
        3. Choose the option to reset your password.
        4. Create a new, secure password of your choice.
        5. Save the changes to update your password.

        If you have any questions or need further assistance, please don't hesitate to contact our support team at nileshgurav1718@gmail.com or 7090026528.

        Thank you for choosing ChatSonic.

        Best regards,
        ChatSonic
        """
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "Password Reset"
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.office365.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()

        return jsonify({'success': True, 'message': 'Password Changed Successfully','otp':otp})
    else:
        return jsonify({'success': False, 'message': 'Email address does not exist'})

@app.route('/get_response', methods=['POST'])
def chatbot_response():
    try:
        user_input = request.json['user_input']  
        response = get_response(user_input, data)
        return jsonify({'response': response})
    except KeyError:
        return jsonify({'error': 'Invalid request data'})

@app.route('/sign_up', methods=['POST'])
def sign_up():
    try:
        username_to_check = request.form['name']
        useremail_to_check = request.form['email']
        password_to_check = request.form['password']
        useremail_to_check = useremail_to_check.replace(" ", "")
    except KeyError:
        return jsonify({'success': False, 'message': 'Invalid form data'})

    value_to_check = useremail_to_check

    cursor = mysql.connection.cursor()
    query = "SELECT COUNT(*) FROM users WHERE email = %s"
    cursor.execute(query, (value_to_check,))
    result = cursor.fetchone()
    cursor.close()
    if result[0] > 0:
        return jsonify({'success': False, 'message': 'Email is already Registered','flag':1})    

    characters = string.ascii_letters + string.digits
    v_otp=""
    v_otp = ''.join(random.choice(characters) for _ in range(6))
    
    sender_email = "nilesh1718@outlook.com"
    receiver_email = useremail_to_check
    password = "Nilesh@cs046"

    body = f"""
    Dear {username_to_check}

    We hope this email finds you well.

    Your otp is {v_otp}

    Please enter the otp and verify your email address

    If you have any questions or need further assistance, please don't hesitate to contact our support team at nileshgurav1718@gmail.com or 7090026528.

    Thank you for choosing ChatSonic.

    Best regards,
    ChatSonic
    """

    msg = MIMEMultipart('alternative')
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "OTP Verification"
    msg.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP('smtp.office365.com', 587)
    server.starttls()
    server.login(sender_email, password)
    server.sendmail(sender_email, receiver_email, msg.as_string())
    server.quit()

    return jsonify({'success': True, 'message': 'OTP Sent Successfully','otp':v_otp})

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    username_to_enter = request.form['name']
    useremail_to_enter = request.form['email']
    password_to_enter = request.form['password']
    utype=0
    cursor = mysql.connection.cursor()
    sql_query = "INSERT INTO users (email, name, password, utype) VALUES (%s, %s, %s, %s)"
    values = (useremail_to_enter, username_to_enter, password_to_enter, utype)
    cursor.execute(sql_query, values)
    mysql.connection.commit()
    cursor.close()

    return jsonify({'success': True, 'message': 'User created successfully'})

@app.route('/login', methods=['POST'])
def login():
    try:
        username_to_check = request.form['email']
        password_to_check = request.form['password']
    except KeyError:
        return jsonify({'success': False, 'message': 'Invalid form data'})

    cursor = mysql.connection.cursor()
    query = "SELECT * FROM users WHERE email = %s"
    cursor.execute(query, (username_to_check,))
    user = cursor.fetchone()
    cursor.close()

    if user:
        if user[2] == password_to_check:
            session['user_id'] = user[0]
            return jsonify({'success': True, 'redirect': url_for('home'), 'message': 'User exists and password is correct'})
        else:
            return jsonify({'success': False, 'message': 'User exists but password is incorrect'})
    else:
        return jsonify({'success': False, 'message': 'User does not exist'})

@app.route('/get_user', methods=['POST'])
def get_user():
    user=session.get('user_id')
    cursor = mysql.connection.cursor()
    query = "SELECT * FROM users WHERE email = %s"
    cursor.execute(query, (user,))
    userarray = cursor.fetchone()
    cursor.close()
    if user:
        return jsonify({'success': True, 'user': user,'pwd_reset':userarray[3],'user_name':userarray[1]})
    else:
        return jsonify({'success': False, 'user': user})

@app.route('/set_password', methods=['POST'])
def set_password():
    email=request.form['user']
    new_password=request.form['password']
    cur = mysql.connection.cursor()
    update_query = "UPDATE users SET password = %s, password_reset = %s WHERE email = %s"
    cur.execute(update_query, (new_password,0, email))
    mysql.connection.commit()
    cur.close()
    return jsonify({'success': True, 'message': 'Password Changed Successfully'})

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    audio_file_path = 'temp_audio.wav'
    audio_file.save(audio_file_path)

    try:
        result = model.transcribe(audio_file_path)
        transcription = result["text"]
        return jsonify({'transcription': transcription}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)

@app.route('/get_prompt_questions', methods=['GET'])
def get_prompt_questions():
    return jsonify({"questions": prompt_questions})

@app.route('/load_chathistory', methods=['POST'])
def load_chathistory():
    user_email=session.get('user_id')
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT question,answer FROM chat_history WHERE user_email = %s ORDER BY time DESC LIMIT 5", (user_email,))
    rows = cursor.fetchall()
    cursor.close()

    json_data = [{'message': msg, 'reply': reply} for msg, reply in rows]
    return jsonify(json_data)

@app.route('/home')
def home():
    if 'user_id' in session:
        return render_template('home.html')
    else:
        return redirect(url_for('index'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Redirect User to Login Page', 'redirect': url_for('index')})

@app.errorhandler(500)
def internal_server_error(e):
    return "An internal server error occurred", 500

if __name__ == '__main__':
    app.run(debug=True)
