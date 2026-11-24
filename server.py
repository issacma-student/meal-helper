import random

import requests
from flask import Flask, render_template, jsonify

app = Flask(__name__)

MEALDB_API = "https://www.themealdb.com/api/json/v1/1"
REQUEST_TIMEOUT_SECONDS = 10
# TheMealDB stores ingredients in strIngredient1..strIngredient20
MAX_INGREDIENTS = 20


def get_recipe_for(main_ingredient: str) -> dict | None:
    """
    Fetch a random recipe with a specified main ingredient.
    The recipes are requested from "themealdb" API.
    Returns None if TheMealDB has no meal with this ingredient.
    """
    # 1. Fetch the list of meals that contain the ingredient.
    response = requests.get(f"{MEALDB_API}/filter.php",
                            params={"i": main_ingredient},
                            timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    meals = response.json()["meals"]  # a list, or None when nothing matches
    if not meals:
        return None

    # 2. Choose a random meal from the list (the list only has name, image and id).
    chosen_meal = random.choice(meals)

    # 3. Fetch the full recipe of the chosen meal by its id.
    response = requests.get(f"{MEALDB_API}/lookup.php",
                            params={"i": chosen_meal["idMeal"]},
                            timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    full_meal = response.json()["meals"][0]

    # 4. Convert TheMealDB's format to ours.
    return dict(
        name=full_meal["strMeal"],
        image=full_meal["strMealThumb"],
        video=full_meal.get("strYoutube") or "",
        instructions=full_meal["strInstructions"],
        ingredients=extract_ingredients(full_meal),
    )


def extract_ingredients(full_meal: dict) -> dict[str, str]:
    """
    Turn strIngredient1..20 / strMeasure1..20 into {ingredient: measure}.
    Unused slots are "" or None (null) in TheMealDB, so they are skipped.
    """
    ingredients = {}
    for i in range(1, MAX_INGREDIENTS + 1):
        ingredient = (full_meal.get(f"strIngredient{i}") or "").strip()
        measure = (full_meal.get(f"strMeasure{i}") or "").strip()
        if ingredient:
            ingredients[ingredient] = measure
    return ingredients


@app.route('/')
def index():
    """
    Renders and returns the main page HTML.
    """
    return render_template("index.html")


# YOUR CODE HERE:
# Make this endpoint get called when for the following routes: "/recipe/<ingredient>"
def recipe(ingredient):
    """
    Renders and returns an HTML page with a random recipe for a given main ingredient.
    """
    # BONUS:
    # If there are no meals for a given ingredient, return a 404 NOT FOUND error response.
    # Hint: Read the documentation of flask. This is a bonus :P
    return render_template("recipe.html",
                           ingredient=ingredient,
                           recipe=get_recipe_for(ingredient))


# YOU CODE HERE:
# Add another endpoint:
# Route "/recipe/<ingredient>/json" should return a JSON with the output of `get_recipe_for`.
# Hint: `flask.jsonify()`


# BONUS:
# Add these endpoints:
# 1. "/personal" with POST method:
#    - Receives a recipe JSON in the request body, and adds it to a list of personal recipes.
#    - Make the list persistent in a JSON file.
#    - Redirect the client to the page of the newly saved recipe.
#    - Hint: `flask.request`
#    - Hint 2: `flask.redirect`
#    - Hint 3: Use `requests` to check if it works.
# 2. "/personal/<name>/<int:json>" with GET method:
#    - Returns the recipe page if `json == 0`, or a JSON if `json == 1`.
#    - Return a 404 response for flag values other than 0 or 1.
# 3. "/personal/<name>" with DELETE method:
#    - Delete the recipe with the given name
# 4. "/personal/all" with GET method:
#    - Returns a JSON with the list of personal recipes.


# EXTRA BONUS:
# Change the "/recipe" endpoints above to search the personal list as well.

if __name__ == '__main__':
    app.run(debug=True)
