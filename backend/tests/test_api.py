"""
Script de test per verificar que l'API funciona correctament
Executa: python test_api.py
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_health():
    """Test endpoint /"""
    print("🧪 Test: Health check...")
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    print(f"   ✅ Status: {response.json()['status']}")

def test_config():
    """Test endpoint /api/config"""
    print("\n🧪 Test: Config...")
    response = requests.get(f"{BASE_URL}/api/config")
    assert response.status_code == 200
    data = response.json()
    print(f"   ✅ Professors: {data['num_professors']}")
    print(f"   ✅ Hores: {data['num_hores']}")

def test_professors():
    """Test endpoint /api/professors"""
    print("\n🧪 Test: Llista professors...")
    response = requests.get(f"{BASE_URL}/api/professors")
    assert response.status_code == 200
    data = response.json()
    print(f"   ✅ Total: {len(data['professors'])} professors")
    print(f"   ✅ Primers 5: {data['professors'][:5]}")

def test_hores():
    """Test endpoint /api/hores"""
    print("\n🧪 Test: Llista hores...")
    response = requests.get(f"{BASE_URL}/api/hores")
    assert response.status_code == 200
    data = response.json()
    print(f"   ✅ Total: {len(data['hores'])} hores")
    print(f"   ✅ Hores: {data['hores']}")

def test_substitucions():
    """Test endpoint /api/substitucions/{data}"""
    data = datetime.now().strftime("%Y-%m-%d")
    print(f"\n🧪 Test: Substitucions del {data}...")
    response = requests.get(f"{BASE_URL}/api/substitucions/{data}")
    assert response.status_code == 200
    substitucions = response.json()
    print(f"   ✅ Total: {len(substitucions)} substitucions")
    if substitucions:
        print(f"   ✅ Primera: {substitucions[0]}")

def test_generar_substitucions():
    """Test endpoint POST /api/substitucions/{data}/generar"""
    data = datetime.now().strftime("%Y-%m-%d")
    print(f"\n🧪 Test: Generar substitucions del {data}...")
    response = requests.post(f"{BASE_URL}/api/substitucions/{data}/generar")
    assert response.status_code == 200
    result = response.json()
    print(f"   ✅ {result['message']}")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTS API - Gestor Substitucions")
    print("=" * 60)

    try:
        test_health()
        test_config()
        test_professors()
        test_hores()
        test_substitucions()
        # test_generar_substitucions()  # Descomenteu si voleu provar generació

        print("\n" + "=" * 60)
        print("✅ TOTS ELS TESTS HAN PASSAT!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: No es pot connectar al servidor")
        print("   Assegura't que el backend està executant a http://localhost:8000")
        print("   Executa: python main.py")

    except AssertionError as e:
        print(f"\n❌ TEST FALLIT: {e}")

    except Exception as e:
        print(f"\n❌ ERROR INESPERAT: {e}")
