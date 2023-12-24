from flask import Flask, render_template
import folium 

app = Flask(__name__)

@app.route('/')
def index():
    
    map_obj = folium.Map(location=[48.8566, 2.3522], zoom_start=13)
    folium.Marker([48.8566, 2.3522],zoom_start=13)
    folium.Marker([48.8566, 2.3522], popup='Hello, Leafet! This is a sample marker .').add_to(map_obj)

    return render_template('lec16-mapIndex.html',map_content=map_obj._repr_html_())
if __name__ == '__main__':
    app.run(debug=True)