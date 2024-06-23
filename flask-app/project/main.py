from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from . import db
from .models import User, Article, Purchase
import stripe
from datetime import datetime
import webbrowser
import time
import json
import boto3
from PIL import Image
import base64
import io
import logging
import os


main = Blueprint("main", __name__)

def translate_title(title):
    modelId = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
    AWS_KEY = os.getenv("AWS_KEY")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
    bedrock_runtime = boto3.client(service_name='bedrock-runtime', 
    region_name='us-east-1', 
    aws_access_key_id=AWS_KEY, 
    aws_secret_access_key=AWS_SECRET_KEY)
    ### parameters for the LLM to control text-generation
    # temperature increases randomness as it increases
    temperature = 0.5
    # top_p increases more word choice as it increases
    top_p = 1
    # maximum number of tokens togenerate in the output
    max_tokens_to_generate = 250
    messages = [{"role": "user", "content": title}]
    body = json.dumps({
        "messages": messages,
        "system": "画像生成のプロンプトに使えるように英訳して下さい。そのままプロンプトに使用するので余計な文字を含まないようにして下さい。",
        "max_tokens": max_tokens_to_generate,
        "temperature": temperature,
        "top_p": top_p,
        "anthropic_version": "bedrock-2023-05-31"
    })
    response = bedrock_runtime.invoke_model(body=body, modelId=modelId, accept="application/json", contentType="application/json")
    response_body = json.loads(response.get('body').read())
    result = response_body.get('content', '')
    return result[0]['text']


def generate_image(model_id, prompt, path):
    # AWSのサービスクライアントを作成（リージョン指定）
    AWS_KEY = os.getenv("AWS_KEY")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
    bedrock_runtime = boto3.client(service_name='bedrock-runtime', 
    region_name='us-east-1', 
    aws_access_key_id=AWS_KEY, 
    aws_secret_access_key=AWS_SECRET_KEY)
    
    # リクエストボディの作成
    body = json.dumps({
        "text_prompts": [{"text": prompt}],
        "cfg_scale": 10,
        "seed": 0,
        "steps": 50,
        "samples": 1,
        "style_preset": "photographic"
    })

    # モデルにリクエストを送信
    response = bedrock_runtime.invoke_model(
        body=body, modelId=model_id, 
        accept="application/json", contentType="application/json"
    )

    # 応答から画像データを抽出
    response_body = json.loads(response.get("body").read())
    base64_image = response_body.get("artifacts")[0].get("base64")
    image_bytes = base64.b64decode(base64_image.encode('ascii'))

    # 画像の保存
    image = Image.open(io.BytesIO(image_bytes))
    image.save(path)



@main.route("/chat", methods=["POST"])
@login_required
def chat():
    modelId = 'anthropic.claude-3-5-sonnet-20240620-v1:0'
    AWS_KEY = os.getenv("AWS_KEY")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
    bedrock_runtime = boto3.client(service_name='bedrock-runtime', 
    region_name='us-east-1', 
    aws_access_key_id=AWS_KEY, 
    aws_secret_access_key=AWS_SECRET_KEY)
    ### parameters for the LLM to control text-generation
    # temperature increases randomness as it increases
    temperature = 0.5
    # top_p increases more word choice as it increases
    top_p = 1
    # maximum number of tokens togenerate in the output
    max_tokens_to_generate = 250
    user_input = request.json.get("input", "")
    messages = [{"role": "user", "content": user_input}]
    body = json.dumps({
        "messages": messages,
        "system": "日本語で答えてください。",
        "max_tokens": max_tokens_to_generate,
        "temperature": temperature,
        "top_p": top_p,
        "anthropic_version": "bedrock-2023-05-31"
    })

    response = bedrock_runtime.invoke_model(body=body, modelId=modelId, accept="application/json", contentType="application/json")
    response_body = json.loads(response.get('body').read())
    result = response_body.get('content', '')

    return jsonify({"response": result})

@main.route("/chat_page")
def chat_page():
    return render_template("chat.html")


@main.route("/profile")
@login_required
def profile():
    user_info = {
        "username": current_user.username,
        "email": current_user.email,
    }
    return render_template("profile.html", user_info=user_info)


@main.route("/create_post")
@login_required
def create():
    return render_template("create_post.html")


def generate_preview(content, max_length=55):
    if len(content) <= max_length:
        return content
    else:
        return content[:max_length] + "..."


@main.route("/")
def index():
    preview_articles = []
    articles = Article.query.all()
    for article in articles:
        preview_content = generate_preview(article.content)
        
        # ファイルが存在するか確認
        if not os.path.isfile(f'project/static/images/thumbnail/{article.id}.jpg'):
            image_path = 'images/logo.png'
        else:
            image_path = f'images/thumbnail/{article.id}.jpg'

        preview_articles.append({
            "title": article.title,
            "content": preview_content,
            "date": article.date,
            "price": article.price,
            "id": article.id,
            "user_id": article.user_id,
            "image_path": image_path
        })
    return render_template("index.html", articles=preview_articles)


@main.route("/checkout/<int:article_id>", methods=["POST"])
@login_required
def checkout(article_id):
    article = Article.query.get_or_404(article_id)
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "jpy",
                    "product_data": {
                        "name": article.title,
                    },
                    "unit_amount": article.price,  # 価格はセント単位
                },
                "quantity": 1,
            }
        ],
        mode="payment",
        success_url=url_for("main.success", article_id=article.id, _external=True)
        + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=url_for("main.index", _external=True),
    )
    return redirect(session.url, code=303)


@main.route("/success/<int:article_id>")
@login_required
def success(article_id):
    session_id = request.args.get("session_id")
    session = stripe.checkout.Session.retrieve(session_id)

    # 購入記録をデータベースに保存
    purchase = Purchase(
        post_id=article_id,
        user_id=current_user.id,
        date=datetime.utcnow(),
        session_id=session_id,
    )
    db.session.add(purchase)
    db.session.commit()

    flash("Purchase successful!")
    return redirect(url_for("main.article", article_id=article_id))


@main.route("/article/<int:article_id>")
@login_required
def article(article_id):
    article = Article.query.get_or_404(article_id)
    if not os.path.isfile(f'project/static/images/thumbnail/{article.id}.jpg'):
        image_path = 'images/logo.png'
    else:
        image_path = f'images/thumbnail/{article.id}.jpg'
    purchase = Purchase.query.filter_by(
        user_id=current_user.id, post_id=article_id
    ).first()
    return render_template(
        "article.html", article=article, purchase=purchase is not None, path=image_path
    )


@main.route("/mypage")
@login_required
def mypage():
    preview_articles = []
    articles = Article.query.all()
    user_info = {
        "username": current_user.username,
        "email": current_user.email,
        # 他の必要なユーザー情報を追加
    }
    for article in articles:
        preview_content = generate_preview(article.content)
        preview_articles.append(
            {
                "id": article.id,
                "title": article.title,
                "content": preview_content,
                "date": article.date,
                "price": article.price,
            }
        )

    return render_template(
        "mypage.html", articles=preview_articles, user_info=user_info
    )

@main.route("/posted")
@login_required
def posted():
    posted_articles = []
    articles = Article.query.filter_by(user_id=current_user.id).all()
    for article in articles:
        preview_content = generate_preview(article.content)
        # ファイルが存在するか確認
        if not os.path.isfile(f'project/static/images/thumbnail/{article.id}.jpg'):
            image_path = 'images/logo.png'
        else:
            image_path = f'images/thumbnail/{article.id}.jpg'
        posted_articles.append(
            {
                "id": article.id,
                "title": article.title,
                "content": preview_content,
                "date": article.date,
                "price": article.price,
                "image_path": image_path
            }
        )
        user_info = {
            "username": current_user.username,
        }
    return render_template(
        "posted.html", posted_articles=posted_articles, user_info=user_info
    )


@main.route("/purchased")
@login_required
def purchased():
    purchased_articles = []
    purchases = Purchase.query.filter_by(user_id=current_user.id).all()

    # 購入された記事のIDを取得して、関連する記事を取得
    for purchase in purchases:
        article = Article.query.filter_by(id=purchase.post_id).first()
         # ファイルが存在するか確認
        if not os.path.isfile(f'project/static/images/thumbnail/{article.id}.jpg'):
            image_path = 'images/logo.png'
        else:
            image_path = f'images/thumbnail/{article.id}.jpg'
        
        if article:
            purchased_articles.append(
                {
                "id": article.id,
                "title": article.title,
                "content": article.content,
                "date": article.date,
                "price": article.price,
                "image_path": image_path
            }
            )

    user_info = {
        "username": current_user.username,
    }
    return render_template(
        "purchased.html", purchased_articles=purchased_articles, user_info=user_info
    )


@main.route("/create_post", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        price = request.form.get("price")

        if not title or not content or not price:
            flash("All fields are required!")
            return redirect(url_for("main.create"))

        existing_post = Article.query.filter_by(title=title).first()
        if existing_post:
            flash("A post with this title already exists!", "error")
            return redirect(url_for("main.create"))

        new_post = Article(
            title=title,
            content=content,
            price=float(price),
            user_id=current_user.id,
            date=datetime.utcnow(),
        )
        db.session.add(new_post)
        db.session.commit()

        #タイトルを翻訳してgenerate_imageのプロンプトにする
        prompt=translate_title(title)


        # 画像を生成し保存する
        image_path = f"project/static/images/thumbnail/{new_post.id}.jpg"
        generate_image('stability.stable-diffusion-xl-v1', prompt, image_path)

        flash("Post created successfully!", "success")
        return redirect(url_for("main.post_success"))
    return render_template("create_post.html")


@main.route("/post_success")
@login_required
def post_success():
    return render_template("flash_message.html")


@main.route("/edit_post/<int:article_id>", methods=["GET", "POST"])
@login_required
def edit_post(article_id):
    article = Article.query.get_or_404(article_id)

    if article.user_id != current_user.id:
        flash("You do not have permission to edit this post.", "error")
        return redirect(url_for("main.posted"))

    if request.method == "POST":
        if "save" in request.form:
            article.title = request.form.get("title")
            article.content = request.form.get("content")
            article.price = request.form.get("price")

            if not article.title or not article.content or not article.price:
                flash("All fields are required!", "error")
                return redirect(url_for("main.edit_post", article_id=article_id))

            db.session.commit()
            flash("Post updated successfully!", "success")
            return redirect(url_for("main.posted"))
        elif "delete" in request.form:
            db.session.delete(article)
            db.session.commit()
            flash("Post deleted successfully!", "success")
            return redirect(url_for("main.posted"))

    return render_template("edit_post.html", article=article)


@main.route("/delete_post/<int:article_id>", methods=["POST"])
@login_required
def delete_post(article_id):
    article = Article.query.get_or_404(article_id)

    if article.user_id != current_user.id:
        flash("You do not have permission to delete this post.", "error")
        return redirect(url_for("main.posted"))

    db.session.delete(article)
    db.session.commit()
    flash("Post deleted successfully!", "success")
    return redirect(url_for("main.posted"))
