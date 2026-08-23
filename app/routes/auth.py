from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login_form():
    if session.get("authed"):
        return redirect("/")
    return render_template("login.html", error=False)


@auth_bp.post("/login")
def login_submit():
    if request.form.get("password") == current_app.config["APP_PASSWORD"]:
        session["authed"] = True
        return redirect(request.args.get("next") or "/")
    return render_template("login.html", error=True), 401


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_form"))
