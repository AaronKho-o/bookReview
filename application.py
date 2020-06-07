import os
import requests

from flask import Flask, session, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

#registration page
@app.route("/")
def index():
    return render_template("index.html", message = "")

#registering a new user
@app.route("/register", methods = ["POST"])
def register():
    username = request.form["username"]
    if (username == ""):
        return render_template("index.html", message = "Invalid username")
    checkuser = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()
    if (checkuser != None):
        return render_template("index.html", message = "Sorry! This username already exists")
    password = request.form["password"]
    db.execute("INSERT INTO users (username, password) VALUES (:username, :password)",
            {"username": username, "password": password})
    db.commit()
    return render_template("index.html", message="Account created, you can now login!")

#login
@app.route("/login", methods = ["GET", "POST"])
def login():
    if (request.method=="GET"):
        return render_template("login.html", message="")
    if(request.method=="POST"):
        username = request.form["username"]
        checkuser = db.execute("SELECT * FROM users WHERE username = :username", {"username":username}).fetchone()
        if (checkuser == None):
            return render_template("index.html", message = "Username does not exist")
        else:
            password = request.form["password"]
            if (password == checkuser.password):
                #start the session
                session["user"] = username
                session["results"] = []
                col_names=None
                return render_template("home.html", results=session["results"], col_names = col_names)
            else:
                return render_template("login.html",message="Password was not recognized")

#open the home page
@app.route("/home")
def home():
    if (session["results"] == []):
        col_names = None
        return render_template("home.html", results=session["results"], col_names = col_names)
    else:
        col_names = ["ISBN", "TITLE", "AUTHOR","YEAR"]
        return render_template("home.html", results=session["results"], col_names = col_names)

#searching for books via the column name selected by the user
@app.route("/search", methods = ["POST"])
def search():
    key_words = request.form["key_words"]
    if (key_words == ""):
        col_names = None
        return render_template("home.html", results = session["results"], message = "", col_names=col_names)
    book_col = request.form["book_col"].strip()
    if (book_col== "author"):
        results = db.execute("SELECT * FROM books WHERE author iLIKE :key_words", {"key_words":f'%{key_words}%'}).fetchall()
    if (book_col== "isbn"):
        results = db.execute("SELECT * FROM books WHERE isbn iLIKE :key_words", {"key_words":f'%{key_words}%'}).fetchall()
    if (book_col== "title"):
        results = db.execute("SELECT * FROM books WHERE title iLIKE :key_words", {"key_words":f'%{key_words}%'}).fetchall()

    session["results"]=results

    if (session["results"] == []):
        col_names = None
        return render_template("home.html", results = session["results"], message = "No matching books.", col_names=col_names)
    else:
        col_names = ["ISBN", "TITLE", "AUTHOR","YEAR"]
        return render_template("home.html", results = session["results"], messager="", col_names=col_names)

#information of a specific book
@app.route("/bookdetails/<string:isbn>", methods = ["GET", "POST"])
def bookdetails(isbn):
        book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn":isbn}).fetchone()
        if (book is None):
            return render_template("error.html")

        reviews = db.execute("SELECT username, review, rating FROM reviews WHERE isbn= :isbn", {"isbn":isbn}).fetchall()
        if (request.method == "GET"):
            if (reviews is None):
                message = "No reviews yet"
            else:
                message = ""
        if (request.method == "POST"):
            checkreview = db.execute("SELECT * FROM reviews WHERE isbn = :isbn AND username = :username", {"isbn":isbn, "username":session.get("user")}).fetchone()
            if (checkreview != None):
                message = "Review has already been made"
            else:
                db.execute("INSERT INTO reviews (isbn, review, rating, username) VALUES (:isbn, :review,:rating, :username)",
                        {"isbn":isbn, "review":request.form["review"], "rating":request.form["rating"], "username": session.get("user")})
                db.commit()
                reviews = db.execute("SELECT username, review, rating FROM reviews WHERE isbn= :isbn", {"isbn":isbn}).fetchall()
                message = "Review made!"


        #Goodreads Review Data (Json)
        try:
            res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key":"C5s6m4nWdXqGdwdQrazqw", "isbns": isbn})
            data = res.json()
            num_of_ratings = data["books"][0]['work_ratings_count']
            average_rating = data["books"][0]['average_rating']
        except:
            num_of_ratings = "Not found"
            average_rating = "Not found"

        return render_template("bookdetails.html", book = book, reviews = reviews, message = message, average_rating = average_rating, num_of_ratings = num_of_ratings)


#API Access
@app.route("/api/<string:isbn>", methods = ["GET"])
def books_api(isbn):
    '''Return  a JSON response containing the book’s title, author, publication date, ISBN number, review count, and average score.'''

    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn":isbn}).fetchone()
    if (book is None):
        return jsonify({"error": "ISBN was not found"}), 404

    reviews = db.execute("SELECT review, rating FROM reviews WHERE isbn=:isbn", {"isbn":isbn}).fetchall()
    count = 0
    rating = 0
    for review in reviews:
        count += 1
        rating += review.rating
    if (count == 0):
        return jsonify({
            "title":book.title,
            "author":book.author,
            "year":book.year,
            "isbn":isbn,
            "review_count":count,
            "average_score":0
        })
    else:
        return jsonify({
            "title":book.title,
            "author":book.author,
            "year":book.year,
            "isbn":isbn,
            "review_count":count,
            "average_score":rating/count
        })


#logout
@app.route("/logout", methods = ["GET"])
def logout():
    session.clear() #end session
    return render_template("login.html", message="")
