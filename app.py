from flask import Flask, send_from_directory

app = Flask(__name__, static_folder="docs/build/html", static_url_path="")


# Serve index.html at root
@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    # TODO: For production, use gunicorn instead
    app.run(host="0.0.0.0", port=5000)
