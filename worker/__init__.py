"""The auto-apply worker. Runs as its own Railway service, not in the web app.

Nothing in here is imported by main.py. The dependency goes one way: the
worker imports the app so that there is exactly one definition of every
model, every cap and the question normaliser — and the web image never has
to carry Chromium.
"""
