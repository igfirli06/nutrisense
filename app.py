from flask import Flask, render_template, request, jsonify
# import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
import json
from sklearn.neighbors import NearestNeighbors
from flask_cors import CORS
import logging


app = Flask(__name__)
CORS(app, resources={r"/predict": {"origins": "http://127.0.0.1:5000"}})
logging.basicConfig(level=logging.DEBUG)

file_path = 'model/recipe_final1.csv'
recipe_df = pd.read_csv(file_path)

file_path = 'model/list_bahan.csv'
all_bahan = pd.read_csv(file_path)
bahan = all_bahan['Ingredients'].tolist()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/kalkulator')
def kalkulator():
    return render_template('kalkulator.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        
        data = request.json
        gender = data['gender']
        umur = int(data['age'])
        list_bahan = data['ingredients']
        

        # Validate age
        if umur < 7 or umur > 12:
            return jsonify({'error': 'Umur tidak termasuk anak SD (7-12 tahun)'})

        if list_bahan not in bahan:
            return jsonify({'error': 'Bahan tidak tersedia didalam dataset'})
        
        gender_encoded = 1 if gender == 'male' else 0

        # Nutrition categories
        data_nutrisi = [
            [13.3, 18.3, 7.8],
            [16.7, 21.7, 9.3],
            [18.3, 21.7, 9.0]
        ]
        
        if umur < 7:
            print("maaf umur tidak termasuk anak sd")
        elif umur < 10:
            kategori = 0
        elif umur < 13:
            if gender == 1: #1 untuk laki laki dan 0 untuk perempuan
                kategori = 1
            else:
                kategori = 2
        else:
            print("maaf umur tidak termasuk anak sd")
        
        menu_bergizi1 = recipe_df[recipe_df.protein > data_nutrisi[kategori][0]]
        menu_bergizi2 = menu_bergizi1[menu_bergizi1.fat > data_nutrisi[kategori][1]]
        menu_bergizi3 = menu_bergizi2[menu_bergizi2.fiber > data_nutrisi[kategori][2]]

        vectorizer = TfidfVectorizer()
        X_ingredients = vectorizer.fit_transform(menu_bergizi3['ingredients_list'])
        nn = NearestNeighbors(n_neighbors=5, metric='euclidean')
        nn.fit(X_ingredients.toarray())
        
        # merekomendasikan resep
        input_ingredients_transformed = vectorizer.transform([list_bahan])
        distances, indices = nn.kneighbors(input_ingredients_transformed.toarray())
        recommendations = menu_bergizi3.iloc[indices[0]]
        
        # Prepare response
        prediction = recommendations.head(3)[['recipe_name', 'ingredients_list', 'image_url']]

        # json_data = list_bahan.to_json(orient='records')
        json_data = prediction.to_json(orient='records')
        
        return jsonify({'prediction': json.loads(json_data)})

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
