"""
Modifications by Andrei Cozma which are based on the original code from the following repository:
https://github.com/scottquach/Canvas-Assignments-Transfer-For-Todoist

What's new:
- Use the 'canvasapi' library instead of requests for shorter/cleaner code
- Use the 'pick' library for better multiple-item selection
- Added ability to rename a course as it appears as a Todoist project (can optionally use the default name from Canvas)
- Automatically set task priority based on keywords (configurable)
- Print short and detailed summaries after assignment transfer.
  - Shows counts of new assignments, updated assignments, and skipped assignments (already submitted or already up to date)
- Reformatted print statements for better verbosity and readability.


Huge thanks to scottquach and stacksjb for their awesome work on this project.
"""

import json
from datetime import datetime
from operator import itemgetter

import requests
from canvasapi import Canvas
from pick import pick
from todoist.api import TodoistAPI

# Loaded configuration files
config_fn = "config.json"
config = {}
header = {}
param = {'per_page': '100', 'include': 'submission'}
course_ids = {}
assignments = []
todoist_tasks = []
courses_id_name_dict = {}
todoist_project_dict = {}

input_prompt = "> "


def main():
    print("###################################################")
    print("#     Canvas-Assignments-Transfer-For-Todoist     #")
    print("###################################################\n")
    initialize_api()
    select_courses()

    load_todoist_projects()
    load_assignments()
    load_todoist_tasks()
    create_todoist_projects()
    transfer_assignments_to_todoist()
    print("# Finished!")


def initialize_api():
    """
    Makes sure that the user has their API Keys set up and sets API variables
    """
    global config
    global todoist_api

    with open(config_fn) as config_file:
        config = json.load(config_file);
    if len(config['todoist_api_key']) == 0:
        print("Your Todoist API key has not been configured!\n"
              "To add an API token, go to your Todoist settings and "
              "copy the API token listed under the Integrations Tab.\n"
              "Copy the token and paste below when you are done.")
        config['todoist_api_key'] = input(input_prompt)
        with open(config_fn, "w") as outfile:
            json.dump(config, outfile)
    if (len(config['canvas_api_key'])) == 0:
        print("Your Canvas API key has not been configured!\n"
              "To add an API token, go to your Canvas settings and"
              "click on New Access Token under Approved Integrations.\n"
              "Copy the token and paste below when you are done.")
        config['canvas_api_key'] = input(input_prompt)
        with open(config_fn, "w") as outfile:
            json.dump(config, outfile)

    # create todoist_api object globally
    todoist_api = TodoistAPI(config['todoist_api_key'].strip())
    todoist_api.reset_state()
    todoist_api.sync()
    header.update({"Authorization": "Bearer " + config['canvas_api_key'].strip()})
    print("# API INITIALIZED")


def select_courses():
    """
    Allows the user to select the courses that they want to transfer while generating a dictionary
    that has course ids as the keys and their names as the values
    """
    global config
    print("# Fetching courses from Canvas:")
    canvas = Canvas("https://canvas.instructure.com", config['canvas_api_key'])
    courses_pag = canvas.get_courses()

    i = 1
    for c in courses_pag:
        try:
            courses_id_name_dict[c.id] = f"{c.course_code.replace(' ', '')} - {c.name} [ID: {c.id}]"
            i += 1
        except AttributeError:
            print("  - Skipping invalid course entry.")

    print(f"=> Found {len(courses_id_name_dict)} courses")

    if config['courses']:
        print()
        print("# You have previously selected courses:")
        for i, (c_id, c_name) in enumerate(config['courses'].items()):
            print(f'  {i + 1}. {c_name} [ID: {c_id}]')

        use_previous_input = input("Q: Would you like to use the courses selected last time? (Y/n) ")
        print("")
        if use_previous_input.lower() == "y":
            for c_id, c_name in config['courses'].items():
                course_ids[c_id] = c_name
            return

    title = "Select the course(s) you would like to add to Todoist (press SPACE to mark, ENTER to continue):"

    sorted_ids, sorted_courses = zip(*sorted(courses_id_name_dict.items(), key=itemgetter(0)))

    selected = pick(sorted_courses, title, multiselect=True, min_selection_count=1)

    print("# SELECTED COURSES:")
    print("# If you would like to rename a course as it appears on Todoist, enter the new name below.")
    print("# To use the course name as it appears on Canvas, leave the field blank.")
    for i, (course_name, index) in enumerate(selected):
        course_id = str(sorted_ids[index])
        course_name_prev = course_name
        print(f" {i + 1}) {course_name_prev}")
        course_name_new = input("    - Project Name: ")
        course_ids[course_id] = course_name_new

    # write course ids to config file
    config['courses'] = course_ids
    with open(config_fn, "w") as outfile:
        json.dump(config, outfile)


def load_assignments():
    """
    Iterates over the course_ids list and loads all the users assignments for those classes.
    Appends assignment objects to assignments list.
    """
    for course_id in course_ids:
        response = requests.get(config['canvas_api_heading'] + '/api/v1/courses/' +
                                str(course_id) + '/assignments', headers=header,
                                params=param)
        if response.status_code == 401:
            print('Unauthorized! Check Canvas API Key')
            exit()
        for assignment in response.json():
            assignments.append(assignment)


def load_todoist_tasks():
    """
    Loads all user tasks from Todoist
    """
    tasks = todoist_api.state['items']
    for task in tasks:
        todoist_tasks.append(task)


def load_todoist_projects():
    """
    Loads all user projects from Todoist
    """
    print("# Loading Todoist projects...")
    projects = todoist_api.state['projects']
    for project in projects:
        todoist_project_dict[project['name']] = project['id']


def create_todoist_projects():
    """
    Checks to see if the user has a project matching their course names.
    If there isn't, a new project will be created
    """
    print("# Creating Todoist projects:")
    for i, (course_id, course_name) in enumerate(course_ids.items()):
        if course_name not in todoist_project_dict:
            # TODO: Add option to re-name course names

            project = todoist_api.projects.add(course_name)
            todoist_api.commit()
            todoist_api.sync()

            todoist_project_dict[project['name']] = project['id']
            print(f" - OK: Created Project: \"{course_name}\"")
        else:
            print(f"  {i + 1}. INFO: \"{course_name}\" already exists; skipping...")
    print()


def make_task_title(assignment):
    """
    Creates a task title from an assignment object
    """
    return '[' + assignment['name'] + '](' + assignment['html_url'] + ')'


def get_priority_name(priority: int):
    """
    Returns the name of the priority level
    """
    priorities = {
        1: "Normal",
        2: "Medium",
        3: "High",
        4: "Urgent"
    }
    return priorities[priority]


def find_priority(assignment) -> int:
    """
    Finds the priority level of an assignment
    Task priority from 1 (normal, default value) to 4 (urgent).
    1: Normal, 2: Medium, 3: High, 4: Urgent
    """
    assignment_name = assignment['name']
    assignment_due_at = assignment['due_at']
    priority = 1

    keywords = {
        4: ['exam', 'test', 'midterm', 'final'],
        3: ['project', 'paper', 'quiz', 'homework', 'discussion'],
        2: ['reading', 'assignment']
    }

    for p, keywords in keywords.items():
        if p > priority and any(keyword in assignment_name.lower() for keyword in keywords):
            priority = p

    if assignment_due_at is not None:
        due_at = datetime.strptime(assignment_due_at, '%Y-%m-%dT%H:%M:%SZ')

        # If there are less than 3 days left on the assignment, set priority to 4
        if (due_at - datetime.now()).days < 3:
            priority = 4

    return priority


def check_existing_task(assignment, project_id):
    """
    Checks to see if a task already exists for the assignment.
    Returns flags for whether the task exists and if it needs to be updated,
    as well as the corresponding task object.
    """
    is_added = False
    is_synced = True
    item = None
    for task in todoist_tasks:
        task_title = make_task_title(assignment)
        if task['content'] == task_title and task['project_id'] == project_id:
            is_added = True
            # Check if task is synced by comparing due dates and priority
            if (task['due'] and task['due']['date'] != assignment['due_at']) or \
                    task['priority'] != assignment['priority']:
                is_synced = False
                item = task
                break
    return is_added, is_synced, item


def transfer_assignments_to_todoist():
    """
    Transfers over assignments from Canvas over to Todoist.
    The method Checks to make sure the assignment has not already been transferred to prevent overlap.
    """
    print("# Transferring assignments to Todoist...")

    summary = {'added': [], 'updated': [], 'is-submitted': [], 'up-to-date': []}
    for i, c_a in enumerate(assignments):
        # Get the canvas assignment name, due date, course name, todoist project id
        c_n = c_a['name']
        c_d = c_a['due_at']
        c_cn = course_ids[str(c_a['course_id'])]
        t_proj_id = todoist_project_dict[c_cn]

        # Find the corresponding priority based on the assignment properties
        priority = find_priority(c_a)
        c_a['priority'] = priority

        # Check if the assignment already exists in Todoist and if it needs updating
        is_added, is_synced, item = check_existing_task(c_a, t_proj_id)
        print(f"  {i + 1}. Assignment: \"{c_n}\"")

        # Handle cases for adding and updating tasks on Todoist
        if not is_added:
            if c_a['submission']['submitted_at'] is None:
                add_new_task(c_a, t_proj_id)
                summary['added'].append(c_a)
            else:
                print(f"     INFO: Already submitted, skipping...")
                summary['is-submitted'].append(c_a)
        elif not is_synced:
            update_task(c_a, item)
            summary['updated'].append(c_a)
        else:
            print(f"     OK: Task is already up to date!")
            summary['up-to-date'].append(c_a)
        print(f"     Course: {c_cn}")
        print(f"     Due Date: {c_d}")
        print(f"     Priority: {get_priority_name(priority)}")

    # Commit changes to Todoist
    todoist_api.commit()

    # Print out short summary
    print()
    print(f"# Short Summary:")
    print(f"  * Added: {len(summary['added'])}")
    print(f"  * Updated: {len(summary['updated'])}")
    print(f"  * Already Submitted: {len(summary['is-submitted'])}")
    print(f"  * Up to Date: {len(summary['up-to-date'])}")

    # Print detailed summary?
    print()
    answer = input("Q: Print Detailed Summary? (Y/n): ")
    if answer.lower() == 'y':
        print()
        print(f"# Detailed Summary:")
        for cat, a_list in summary.items():
            print(f"  * {cat.upper()}: {len(a_list)}")
            for i, c_a in enumerate(a_list):
                c_n = c_a['name']
                c_cn = course_ids[str(c_a['course_id'])]
                a_p = c_a['priority']
                a_d = c_a['due_at']
                d = None
                if a_d:
                    d = datetime.strptime(a_d, '%Y-%m-%dT%H:%M:%SZ')
                # Convert to format: May 22, 2022 at 12:00 PM
                d_nat = "Unknown" if d is None else d.strftime('%b %d, %Y at %I:%M %p')
                print(f"    {i + 1}. \"{c_n}\"")
                print(f"         Course: {c_cn}")
                print(f"         Due Date: {d_nat}")
                print(f"         Priority: {get_priority_name(a_p)}")


def add_new_task(c_a, t_proj_id):
    """
    Adds a new task from a Canvas assignment object to Todoist under the project corresponding to project_id
    """
    print(f"     NEW: Adding new Task for assignment")
    task_title = make_task_title(c_a)
    c_d = c_a['due_at']
    c_p = c_a['priority']
    todoist_api.add_item(task_title,
                         project_id=t_proj_id,
                         date_string=c_d,
                         priority=c_p)


def update_task(c_a, t_task):
    """
    Updates an existing task from a Canvas assignment object to Todoist
    """
    print(f"     UPDATE: Updating Task for assignment: ", end='')
    updates_list = []
    # Check if due date has changed
    t_d = t_task['due']['date'] if t_task['due'] else None
    c_d = c_a['due_at']
    if t_d != c_d:
        updates_list.append('due date')
    # Check if priority has changed
    t_p = t_task['priority']
    c_p = c_a['priority']
    # Print changes
    if t_p != c_p:
        updates_list.append('priority')
    print(", ".join(updates_list))
    # Update Todoist task
    t_task.update(due={
        'date': c_d,
    },
        priority=c_p)


if __name__ == "__main__":
    # Main Execution
    main()
