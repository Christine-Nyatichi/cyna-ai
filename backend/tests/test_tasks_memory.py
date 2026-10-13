# ---------- Tasks ----------

def test_tasks_require_login(client):
    assert client.get("/api/tasks").status_code == 401


def test_create_and_list_tasks(client, auth):
    res = client.post("/api/tasks", json={"title": "Finish project"}, headers=auth)
    assert res.status_code == 201
    assert res.get_json()["is_completed"] is False

    tasks = client.get("/api/tasks", headers=auth).get_json()
    assert [t["title"] for t in tasks] == ["Finish project"]


def test_task_title_is_required(client, auth):
    assert client.post("/api/tasks", json={"title": "  "}, headers=auth).status_code == 400


def test_task_title_length_limit(client, auth):
    assert client.post("/api/tasks", json={"title": "x" * 201}, headers=auth).status_code == 400


def test_complete_and_rename_task(client, auth):
    tid = client.post("/api/tasks", json={"title": "Old"}, headers=auth).get_json()["id"]

    done = client.patch(f"/api/tasks/{tid}", json={"is_completed": True}, headers=auth).get_json()
    assert done["is_completed"] is True

    renamed = client.patch(f"/api/tasks/{tid}", json={"title": "New"}, headers=auth).get_json()
    assert renamed["title"] == "New"


def test_completed_tasks_are_listed_last(client, auth):
    first = client.post("/api/tasks", json={"title": "First"}, headers=auth).get_json()["id"]
    client.post("/api/tasks", json={"title": "Second"}, headers=auth)
    client.patch(f"/api/tasks/{first}", json={"is_completed": True}, headers=auth)

    titles = [t["title"] for t in client.get("/api/tasks", headers=auth).get_json()]
    assert titles == ["Second", "First"]


def test_cannot_rename_task_to_empty(client, auth):
    tid = client.post("/api/tasks", json={"title": "Keep"}, headers=auth).get_json()["id"]
    assert client.patch(f"/api/tasks/{tid}", json={"title": ""}, headers=auth).status_code == 400


def test_delete_task(client, auth):
    tid = client.post("/api/tasks", json={"title": "Bye"}, headers=auth).get_json()["id"]
    assert client.delete(f"/api/tasks/{tid}", headers=auth).status_code == 200
    assert client.get("/api/tasks", headers=auth).get_json() == []


def test_users_cannot_touch_each_others_tasks(client, make_user):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")
    tid = client.post("/api/tasks", json={"title": "Private"}, headers=alice).get_json()["id"]

    assert client.patch(f"/api/tasks/{tid}", json={"title": "x"}, headers=bob).status_code == 404
    assert client.delete(f"/api/tasks/{tid}", headers=bob).status_code == 404
    assert client.get("/api/tasks", headers=bob).get_json() == []


# ---------- Memory ----------

def test_memory_requires_login(client):
    assert client.get("/api/memories").status_code == 401


def test_add_and_list_memory(client, auth):
    res = client.post("/api/memories", json={"content": "I study at night"}, headers=auth)
    assert res.status_code == 201
    memories = client.get("/api/memories", headers=auth).get_json()
    assert [m["content"] for m in memories] == ["I study at night"]


def test_memory_cannot_be_empty(client, auth):
    assert client.post("/api/memories", json={"content": " "}, headers=auth).status_code == 400


def test_memory_length_limit(client, auth):
    assert client.post("/api/memories", json={"content": "x" * 301}, headers=auth).status_code == 400


def test_memory_count_limit(client, auth):
    for i in range(50):
        assert client.post("/api/memories", json={"content": f"note {i}"}, headers=auth).status_code == 201
    assert client.post("/api/memories", json={"content": "one too many"}, headers=auth).status_code == 400


def test_delete_one_memory(client, auth):
    mid = client.post("/api/memories", json={"content": "temp"}, headers=auth).get_json()["id"]
    assert client.delete(f"/api/memories/{mid}", headers=auth).status_code == 200
    assert client.get("/api/memories", headers=auth).get_json() == []


def test_clear_all_memories(client, auth):
    client.post("/api/memories", json={"content": "one"}, headers=auth)
    client.post("/api/memories", json={"content": "two"}, headers=auth)
    assert client.delete("/api/memories", headers=auth).status_code == 200
    assert client.get("/api/memories", headers=auth).get_json() == []


def test_users_have_separate_memories(client, make_user):
    alice = make_user("alice", "alice@example.com")
    bob = make_user("bob", "bob@example.com")
    mid = client.post("/api/memories", json={"content": "Alice only"}, headers=alice).get_json()["id"]

    assert client.get("/api/memories", headers=bob).get_json() == []
    assert client.delete(f"/api/memories/{mid}", headers=bob).status_code == 404