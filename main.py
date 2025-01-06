from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash,request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import os
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
app.config['CKEDITOR_LANGUAGE']='en'
ckeditor = CKEditor(app)
Bootstrap5(app)

# Ensure templates are auto-reloaded
gravatar = Gravatar(app,
                size=80,
                rating='g',
                default='retro',
                force_default=False,
                force_lower=False,
                use_ssl=False,
                base_url=None)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# TODO: Configure Flask-Login
login_manager=LoginManager()
login_manager.init_app(app)


# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI','sqlite:///posts.db')
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# TODO: Create a User table for all your registered users. 
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    email:Mapped[str]=mapped_column(String(100),nullable=False,unique=True)
    enc_pass:Mapped[str]=mapped_column(String(100))
    name:Mapped[str]=mapped_column(String(1000))
    posts=relationship('BlogPost',back_populates='author')
    comments=relationship('Comment',back_populates='comment_author')

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id:Mapped[int]=mapped_column(Integer,db.ForeignKey('users.id'))
    author=relationship('User',back_populates='posts')
    comments=relationship('Comment',back_populates='parent_post')

class Comment(db.Model):
    __tablename__='comments'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    text:Mapped[str]=mapped_column(Text,nullable=False)
    author_id:Mapped[int]=mapped_column(Integer,db.ForeignKey('users.id'))
    comment_author=relationship('User',back_populates='comments')
    post_id:Mapped[int]=mapped_column(Integer,db.ForeignKey('blog_posts.id'))
    parent_post=relationship('BlogPost',back_populates='comments')

with app.app_context():
    db.create_all()

def admin_only(func):
    @wraps(func)
    @login_required
    def wrapper(*args,**kwargs):
        if current_user.id!=1:
            return abort(code=403)
        return func(*args,**kwargs)
    return wrapper


@login_manager.user_loader
def load_user(id):
    return User.query.get(id)



# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register',methods=['GET','POST'])
def register():
    form=RegisterForm()
    if form.validate_on_submit():
        user=db.session.execute(db.select(User).where(User.email==form.email.data)).scalar()
        if user:
            flash('You\'ve already signed up with that email, log in instead')
            return redirect(url_for('login'))
        password=form.password.data
        hashed_and_salted=generate_password_hash(password,method='pbkdf2:sha256',salt_length=8)
        new_user=User(email=form.email.data,enc_pass=hashed_and_salted,name=form.name.data)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html",form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login',methods=['GET','POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user=db.session.execute(db.select(User).where(User.email==form.email.data)).scalar()
        if user is not None:
            if check_password_hash(user.enc_pass,form.password.data):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash('Password is incorrect, Please try again.')
                return render_template('login.html',form=form)
        else:
            flash('Email does not exist, Please try again.')
            return render_template('login.html',form=form)
    return render_template("login.html",form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>",methods=['GET','POST'])
def show_post(post_id):
  
    form=CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    all_comments=db.session.execute(db.select(Comment).order_by(Comment.id)).scalars().all()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        comment=Comment(text=form.comment.data,comment_author=current_user,parent_post=requested_post)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('show_post',post_id=post_id))
    return render_template("post.html", post=requested_post,form=form,gravatar=gravatar)


# TODO: Use a decorator so only an admin user can create a new post

@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=True)
