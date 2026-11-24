import json
import random
from pathlib import Path

import requests
from flask import Flask, render_template, jsonify, request, redirect, url_for, abort

app = Flask(__name__)

MEALDB_API = "https://www.themealdb.com/api/json/v1/1"
REQUEST_TIMEOUT_SECONDS = 10
# TheMealDB stores ingredients in strIngredient1..strIngredient20
MAX_INGREDIENTS = 20
REQUEST_TIMEOUT_SECONDS = 10
PERSONAL_RECIPES_FILE = Path(__file__).with_name("personal_recipes.json")


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


def load_personal_recipes() -> list[dict]:
    """Read the personal recipes list from the JSON file ([] if missing)."""
    if not PERSONAL_RECIPES_FILE.exists():
        return []
    with PERSONAL_RECIPES_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def save_personal_recipes(recipes: list[dict]) -> None:
    """Write the whole personal recipes list to the JSON file."""
    with PERSONAL_RECIPES_FILE.open("w", encoding="utf-8") as file:
        json.dump(recipes, file, ensure_ascii=False, indent=2)


def find_personal_recipe(name: str) -> dict | None:
    """Return the personal recipe with this exact name, or None."""
    for saved_recipe in load_personal_recipes():
        if saved_recipe["name"] == name:
            return saved_recipe
    return None


def normalize(ingredient: str) -> str:
    """'Chicken Breast' -> 'chicken_breast' (the format index.html uses)."""
    return ingredient.strip().lower().replace(" ", "_")


def is_safe_link(url: str) -> bool:
    """Allow only empty or http(s) links (blocks 'javascript:' URLs)."""
    return url == "" or url.startswith(("http://", "https://"))


def validate_recipe(data) -> str | None:
    """Return an error message if `data` is not a valid recipe, else None."""
    if not isinstance(data, dict):
        return "Request body must be a JSON object"
    for key in ("name", "image", "video", "instructions"):
        if not isinstance(data.get(key), str):
            return f"'{key}' must be a string"
    if not data["name"].strip() or "/" in data["name"]:
        return "'name' must be non-empty and must not contain '/'"
    ingredients = data.get("ingredients")
    if not isinstance(ingredients, dict) or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in ingredients.items()):
        return "'ingredients' must be an object of {ingredient: measure} strings"
    if not (is_safe_link(data["image"]) and is_safe_link(data["video"])):
        return "'image' and 'video' must be http(s) links"
    return None


def find_recipe(ingredient: str) -> dict | None:
    """
    Return a random recipe that contains `ingredient`,
    from the personal list or TheMealDB.
    Returns None if neither has one.
    """
    wanted = normalize(ingredient)
    personal_matches = [
        saved_recipe for saved_recipe in load_personal_recipes()
        if wanted in map(normalize, saved_recipe["ingredients"])
    ]
    api_recipe = get_recipe_for(ingredient)
    candidates = personal_matches + ([api_recipe] if api_recipe else [])
    if not candidates:
        return None
    return random.choice(candidates)


@app.route('/')
def index():
    """
    Renders and returns the main page HTML.
    """
    return render_template("index.html")


@app.route("/recipe/<ingredient>")
def recipe(ingredient):
    """
    Renders and returns an HTML page with a random recipe
    for a given main ingredient.
    """
    found = find_recipe(ingredient)
    if found is None:
        abort(404, description=f"No recipe found with '{ingredient}'.")
    return render_template("recipe.html",
                           ingredient=ingredient,
                           recipe=found)


@app.route("/recipe/<ingredient>/json")
def recipe_json(ingredient):
    """
    Returns a JSON with a random recipe for a given main ingredient.
    """
    found = find_recipe(ingredient)
    if found is None:
        abort(404, description=f"No recipe found with '{ingredient}'.")
    return jsonify(found)


@app.route("/personal", methods=["POST"])
def add_personal_recipe():
    """
    Save the recipe JSON from the request body to the personal list,
    then redirect the client to the saved recipe's page.
    """
    data = request.get_json(silent=True)  # None if the body isn't valid JSON
    error = validate_recipe(data)
    if error:
        abort(400, description=error)

    # Replace a recipe with the same name instead of storing duplicates.
    recipes = [saved for saved in load_personal_recipes()
               if saved["name"] != data["name"]]
    recipes.append(data)
    save_personal_recipes(recipes)

    # 303 See Other: "the POST worked, now GET this page".
    page_url = url_for("get_personal_recipe", name=data["name"], json=0)
    return redirect(page_url, code=303)


@app.route("/personal/all", methods=["GET"])
def all_personal_recipes():
    """
    Returns a JSON with the list of personal recipes.
    """
    return jsonify(load_personal_recipes())


@app.route("/personal/<name>/<int:json>", methods=["GET"])
def get_personal_recipe(name, json):
    """
    Returns the recipe page if json == 0, or the recipe JSON if json == 1.
    Note: the parameter must be called `json` because the route says <int:json>,
    so inside this function `json` is the number, not the json module.
    """
    saved_recipe = find_personal_recipe(name)
    if saved_recipe is None or json not in (0, 1):
        abort(404)
    if json == 1:
        return jsonify(saved_recipe)
    main_ingredient = normalize(next(iter(saved_recipe["ingredients"]), "anything"))
    return render_template("recipe.html",
                           ingredient=main_ingredient,
                           recipe=saved_recipe)


@app.route("/personal/<name>", methods=["DELETE"])
def delete_personal_recipe(name):
    """
    Delete the recipe with the given name.
    """
    recipes = load_personal_recipes()
    remaining = [saved for saved in recipes if saved["name"] != name]
    if len(remaining) == len(recipes):
        abort(404, description=f"No personal recipe named '{name}'.")
    save_personal_recipes(remaining)
    return jsonify(deleted=name)


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
# 3. "/personal/<name>" with DELETE method:
#    - Delete the recipe with the given name
# 4. "/personal/all" with GET method:
#    - Returns a JSON with the list of personal recipes.


# EXTRA BONUS:
# Change the "/recipe" endpoints above to search the personal list as well.

if __name__ == '__main__':
    app.run(debug=True)
