import random
import string
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename
import os
from flask_migrate import Migrate
from sqlalchemy.orm import relationship
from sqlalchemy import func
from sqlalchemy import Text
from sqlalchemy import func, cast, Integer
import json
from datetime import date

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "school.db")}'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'  
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'} 
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

SCHOOL_PASSWORD = '12345'

# Модель школьных классов (1А - 11В)
class SchoolClass(db.Model):
    __tablename__ = 'school_class'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    class_students = db.relationship(
        'User',
        back_populates='school_class',
        foreign_keys='User.class_id'
    )

    class_mentors = db.relationship(
        'User',
        back_populates='mentor_class',
        foreign_keys='User.mentor_class_id'
    )

parent_student = db.Table('parent_student',
    db.Column('parent_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

teacher_classes = db.Table('teacher_classes',
    db.Column('teacher_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('class_id', db.Integer, db.ForeignKey('school_class.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    birth_date = db.Column(db.Date, nullable=True)
    role = db.Column(db.String(50), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=True)
    mentor_class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=True)
    subjects = db.Column(db.String, nullable=True)
    avatar = db.Column(db.String(200))
    phone = db.Column(db.String(20), nullable=True)
    profile_picture = db.Column(db.String(100), nullable=True)

    # Связи с классами
    school_class = db.relationship(
        'SchoolClass',
        back_populates='class_students',
        foreign_keys=[class_id]
    )

    mentor_class = db.relationship(
        'SchoolClass',
        back_populates='class_mentors',
        foreign_keys=[mentor_class_id]
    )

    teacher_classes = db.relationship(
        'SchoolClass',
        secondary=teacher_classes,
        backref=db.backref('teachers', lazy='dynamic'),
        lazy='dynamic'
    )

    children = db.relationship(
        'User',
        secondary=parent_student,
        primaryjoin=id==parent_student.c.parent_id,
        secondaryjoin=id==parent_student.c.student_id,
        backref='parents'
    )

    def check_password(self, password):
        return check_password_hash(self.password, password)

    @property
    def subjects_list(self):
        return self.subjects.split(',') if self.subjects else []


# Модель расписания
class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    time = db.Column(db.Time, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Связи
    school_class = db.relationship('SchoolClass', backref=db.backref('schedule', lazy=True))
    teacher = db.relationship('User', backref='lessons') 

# Модель оценок
class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id')) 
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'))
    subject = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    student = db.relationship('User', backref='grades', foreign_keys=[student_id])
    school_class = db.relationship('SchoolClass', backref='grades')

# Модель домашнего задания
class Homework(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=False)  
    school_class = db.relationship('SchoolClass', backref=db.backref('homeworks', lazy=True)) 
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    teacher = db.relationship('User', foreign_keys=[teacher_id])

    files = db.Column(db.Text, nullable=True)  

    @property
    def files_list(self):
        if self.files:
            try:
                return json.loads(self.files)
            except Exception:
                return []
        return []

# Модель уведомлений
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=True) 
    notification_type = db.Column(db.String(50), nullable=False)  
    is_read = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='notifications', lazy=True)
    school_class = db.relationship('SchoolClass', backref='notifications', lazy=True)


class PasswordResetRequest(db.Model):
    __tablename__ = 'password_reset_request'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    new_password = db.Column(db.String(200), nullable=True)
    user = db.relationship('User', backref='password_reset_requests')

@login_manager.user_loader
def load_user(user_id):
    user_id = int(user_id)
    return db.session.get(User, user_id)

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        phone = request.form.get('phone')
        user = User.query.filter_by(phone=phone).first()

        if not user:
            flash('Пользователь с таким телефоном не найден.', 'danger')
            return redirect(url_for('reset_password'))

        # Проверка: есть ли уже заявка
        existing = PasswordResetRequest.query.filter_by(user_id=user.id, status='pending').first()
        if existing:
            flash('Заявка уже отправлена. Ожидайте подтверждения.', 'info')
            return redirect(url_for('login'))

        # Создаём заявку
        new_request = PasswordResetRequest(
            user_id=user.id,
            phone=phone,
            ip_address=request.remote_addr,
            created_at=datetime.utcnow()
        )
        db.session.add(new_request)
        db.session.commit()

        flash('Заявка на сброс пароля отправлена. Ожидайте одобрения администратора.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

@app.route('/')
def home():
    return render_template('home.html')


@app.before_request
def require_school_password():
    allowed_routes = ['danger', 'static']
    if not session.get('school_authenticated') and request.endpoint not in allowed_routes:
        return redirect(url_for('danger'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    classes = SchoolClass.query.all()
    subjects = ["Математика", "Русский язык", "Физика", "Химия", "Биология", "История", "География"]

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        class_id = request.form.get('class_id')  
        subjects = request.form.get('subjects')
        phone = request.form.get('phone')

        if class_id:
            class_id = int(class_id)

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        if User.query.filter_by(username=username).first():
            flash('❌ Пользователь с таким именем уже существует!', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, password=hashed_password, role=role, subjects=subjects)
        new_user.phone = phone 

        if role == 'student':
            if not class_id:
                flash('Для ученика нужно выбрать класс!', 'danger')
                return redirect(url_for('register'))

            school_class = SchoolClass.query.get(class_id)
            if not school_class:
                flash('Выбранный класс не существует!', 'danger')
                return redirect(url_for('register'))

            new_user.class_id = school_class.id

        elif role == 'teacher':
            subjects = request.form.getlist('subjects')
            if not subjects:
                flash('Для учителя нужно выбрать хотя бы один предмет!', 'danger')
                return redirect(url_for('register'))
            new_user.subject = json.dumps(subjects)


        db.session.add(new_user)
        db.session.commit()

        flash('✅ Регистрация успешна! Теперь войдите.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', classes=classes, subjects=subjects)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            
            return redirect(url_for('dashboard'))
        else:
            flash('❌ Неверное логин или пароль!', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    print(f"Текущая роль: {current_user.role}")

    children = []
    if current_user.role == 'parent':  
        children = current_user.children 

    return render_template('dashboard.html', username=current_user.username, 
                           role=current_user.role, children=children)

@app.route('/schedule/class-select')
@login_required
def class_select():
    if current_user.role != 'admin':
        return redirect(url_for('schedule'))

    classes = SchoolClass.query.all()
    return render_template('class_select.html', classes=classes)


@app.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    classes = SchoolClass.query.all()
    teachers = User.query.filter_by(role='teacher').order_by(User.last_name).all()
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]

    selected_day = request.args.get('day', days[0]) 
    selected_class_id = request.args.get('selected_class', type=int)
    selected_teacher_id = request.args.get('selected_teacher', type=int)

    if current_user.role == 'admin':
        if selected_class_id:
            session['selected_class_id'] = selected_class_id
        else:
            selected_class_id = session.get('selected_class_id')

        if not selected_class_id:
            return redirect(url_for('class_select'))

    if current_user.role == 'student':
        lessons = Schedule.query.filter_by(day=selected_day, class_id=current_user.class_id).order_by(Schedule.time).all()
    elif current_user.role == 'teacher':
        lessons = Schedule.query.filter_by(day=selected_day, teacher_id=current_user.id).order_by(Schedule.time).all()
    elif current_user.role == 'admin':
        lessons = Schedule.query.filter_by(day=selected_day, class_id=selected_class_id).order_by(Schedule.time).all()
    else:
        lessons = []

    if request.method == 'POST' and current_user.role == 'admin':
        action = request.form.get('action')

        if action == 'add':
            day = request.form.get('day')
            time_str = request.form.get('time')
            subject = request.form.get('subject')
            class_id = request.form.get('class_id')
            teacher_id = request.form.get('teacher')

            if not all([day, time_str, subject, class_id, teacher_id]):
                flash('Все поля должны быть заполнены!', 'danger')
                return redirect(url_for('schedule', day=selected_day, selected_class=selected_class_id))

            try:
                time_obj = datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                flash('Некорректный формат времени!', 'danger')
                return redirect(url_for('schedule', day=selected_day, selected_class=selected_class_id))

            new_lesson = Schedule(
                day=day,
                time=time_obj,
                subject=subject,
                teacher_id=teacher_id,
                class_id=class_id
            )
            db.session.add(new_lesson)
            db.session.commit()

            students = User.query.filter_by(class_id=class_id, role='student').all()
            for student in students:
                db.session.add(Notification(
                    message=f"Добавлен урок: {subject} ({day}, {time_str})",
                    user_id=student.id,
                    notification_type='schedule_updated'
                ))
            db.session.commit()

            flash('✅ Занятие добавлено!', 'success')

        elif action == 'delete':
            schedule_id = request.form.get('schedule_id')
            lesson = Schedule.query.get(schedule_id)

            if lesson:
                students = User.query.filter_by(class_id=lesson.class_id, role='student').all()
                for student in students:
                    db.session.add(Notification(
                        message=f"Удалён урок: {lesson.subject} ({lesson.day}, {lesson.time.strftime('%H:%M')})",
                        user_id=student.id,
                        notification_type='schedule_updated'
                    ))
                db.session.delete(lesson)
                db.session.commit()
                flash('❌ Занятие удалено.', 'success')
            else:
                flash('Занятие не найдено.', 'danger')

        return redirect(url_for('schedule', day=selected_day, selected_class=selected_class_id))

    return render_template(
        'schedule.html',
        lessons=lessons,
        classes=classes,
        teachers=teachers,
        days=days,
        selected_day=selected_day,
        selected_teacher_id=selected_teacher_id,
        selected_class_id=selected_class_id
    )


@app.route('/grades', methods=['GET', 'POST'])
@login_required
def grades():
    if current_user.role == 'teacher':
        classes = current_user.teacher_classes.order_by(
            cast(func.substr(SchoolClass.name, 1, func.length(SchoolClass.name) - 1), Integer),
            func.substr(SchoolClass.name, -1, 1)
        ).all()
    else:
        classes = SchoolClass.query.order_by(
            cast(func.substr(SchoolClass.name, 1, func.length(SchoolClass.name) - 1), Integer),
            func.substr(SchoolClass.name, -1, 1)
        ).all()

    selected_date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

    if current_user.role == 'student':
        student_grades = Grade.query.filter_by(
            student_id=current_user.id,
            date=selected_date_obj
        ).all()
        return render_template(
            'grades.html',
            grades=student_grades,
            is_teacher=False,
            selected_date=selected_date,
            student=current_user
        )

    elif current_user.role == 'teacher':
        selected_class_id = request.args.get('class_id', type=int)
        students = []

        if selected_class_id:
            school_class = db.session.get(SchoolClass, selected_class_id)
            if not school_class:
                flash("Класс не найден.", "danger")
                return redirect(url_for('grades', date=selected_date))

            students = User.query.filter_by(role='student', class_id=selected_class_id).order_by(User.last_name).all()

        if request.method == 'POST':
            try:
                grade_id = request.form.get('grade_id')
                user_id = int(request.form.get('user_id')) 
                subject = request.form.get('subject')
                grade_value = int(request.form.get('grade'))
                date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
                class_id = int(request.form.get('class_id'))

                student = db.session.get(User, user_id)

                if not student or student.role != "student":
                    flash("Ученик не найден!", "danger")
                    return redirect(url_for('grades', class_id=class_id, date=date.strftime('%Y-%m-%d')))

                if student.class_id != class_id:
                    flash("Ошибка: выбранный ученик не принадлежит этому классу.", "danger")
                    return redirect(url_for('grades', class_id=class_id, date=date.strftime('%Y-%m-%d')))

                if grade_value < 1 or grade_value > 5:
                    flash("Оценка должна быть в пределах от 1 до 5.", "danger")
                    return redirect(url_for('grades', class_id=class_id, date=date.strftime('%Y-%m-%d')))

                if grade_id:
                    existing_grade = Grade.query.get(int(grade_id))
                    if existing_grade:
                        if existing_grade.teacher_id != current_user.id:
                            flash("Вы не можете редактировать чужую оценку!", "danger")
                            return redirect(url_for('grades', class_id=class_id, date=date.strftime('%Y-%m-%d')))

                        existing_grade.student_id = student.id
                        existing_grade.class_id = class_id
                        existing_grade.subject = subject
                        existing_grade.grade = grade_value
                        existing_grade.date = date
                        db.session.commit()
                        flash("✅ Оценка обновлена!", "success")
                    else:
                        flash("Оценка не найдена для редактирования.", "danger")
                else:
                    new_grade = Grade(
                        student_id=student.id,
                        class_id=class_id,
                        subject=subject,
                        grade=grade_value,
                        date=date,
                        teacher_id=current_user.id  # <== фиксируем, кто поставил
                    )
                    db.session.add(new_grade)
                    db.session.commit()

                    new_notification = Notification(
                        message=f"Вам поставлена оценка {grade_value} по предмету {subject} за {date.strftime('%d.%m.%Y')}",
                        user_id=student.id,
                        notification_type='grade_added'
                    )
                    db.session.add(new_notification)
                    db.session.commit()

                    flash("✅ Оценка добавлена!", "success")

                return redirect(url_for('grades', class_id=class_id, date=date.strftime('%Y-%m-%d')))

            except ValueError:
                flash("Ошибка: неверный формат данных.", "danger")
            except Exception as e:
                flash(f"Произошла ошибка: {str(e)}", "danger")

        all_grades = Grade.query.filter_by(date=selected_date_obj).filter(
            Grade.teacher_id == current_user.id  # фильтрация по автору
        ).all()


        return render_template(
            'grades.html',
            grades=all_grades,
            classes=classes,
            students=students,
            is_teacher=True,
            selected_date=selected_date
        )

    else:
        flash("Недостаточно прав для доступа к этой странице", "danger")
        return redirect(url_for('home'))


@app.route('/get_students/<int:class_id>', methods=['GET'])
@login_required
def get_students(class_id):
    if current_user.role != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 403

    students = User.query.filter_by(role='student', class_id=class_id).all()
    students_list = [{
        'id': student.id,
        'username': student.username,
        'first_name': student.first_name or '',
        'last_name': student.last_name or ''
    } for student in students]

    return jsonify({'students': students_list})

@app.route('/delete_grade/<int:grade_id>', methods=['POST'])
@login_required
def delete_grade(grade_id):
    if current_user.role != 'teacher':
        flash("У вас нет прав для удаления!", "danger")
        return redirect(url_for('grades'))

    grade = Grade.query.get(grade_id)
    if grade:
        if grade.teacher_id != current_user.id:
            flash("Вы не можете удалить чужую оценку!", "danger")
        else:
            db.session.delete(grade)
            db.session.commit()
            flash("❌ Оценка удалена!", "success")
    else:
        flash("Оценка не найдена.", "danger")

    return redirect(url_for('grades'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы!', 'info')
    return redirect(url_for('login'))

@app.route('/homework', methods=['GET', 'POST'])
@login_required
def homework():
    if current_user.role == 'teacher':
        classes = current_user.teacher_classes.order_by(
            cast(func.substr(SchoolClass.name, 1, func.length(SchoolClass.name) - 1), Integer),
            func.substr(SchoolClass.name, -1, 1)
        ).all()
    else:
        classes = SchoolClass.query.order_by(
            cast(func.substr(SchoolClass.name, 1, func.length(SchoolClass.name) - 1), Integer),
            func.substr(SchoolClass.name, -1, 1)
        ).all()
    current_datetime = datetime.now(timezone.utc)

    selected_date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

    if request.method == 'POST' and 'action' in request.form:
        action = request.form['action']

        if action == 'delete' and current_user.role == 'teacher':
            homework_id = request.form['homework_id']
            homework_to_delete = Homework.query.get(homework_id)
            if homework_to_delete:
                if homework_to_delete.teacher_id != current_user.id:
                    flash('🚫 Вы не можете удалить чужое задание!', 'danger')
                else:
                    db.session.delete(homework_to_delete)
                    db.session.commit()
                    flash('❌ Домашнее задание удалено!', 'success')
            else:
                flash('Ошибка: домашнее задание не найдено.', 'danger')

        elif action == 'edit' and current_user.role == 'teacher':
            homework_id = int(request.form['homework_id'])
            hw = db.session.get(Homework, homework_id)
            if hw:
                if hw.teacher_id != current_user.id:
                    flash('🚫 Вы не можете редактировать чужое задание!', 'danger')
                    return redirect(url_for('homework', date=selected_date))

                hw.class_id   = int(request.form['class_id'])
                hw.subject    = request.form['subject']
                hw.description= request.form['description']
                hw.due_date   = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date()
                db.session.commit()
                flash('✅ Домашнее задание обновлено', 'success')
            else:
                flash('❌ Задание не найдено', 'danger')
            return redirect(url_for('homework', date=selected_date))

        elif action == 'add' and current_user.role == 'teacher':
            subject = request.form['subject']
            description = request.form['description']

            if 'due_date' in request.form:
                try:
                    due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date()
                except ValueError:
                    flash('Неверный формат даты сдачи', 'danger')
                    return redirect(url_for('homework'))
            else:
                flash('Дата сдачи не указана', 'danger')
                return redirect(url_for('homework'))

            created_at = datetime.utcnow()

            class_id = request.form['class_id']

            files = request.files.getlist('files')
            saved_file_paths = []

            save_dir = os.path.join(app.root_path, 'static', 'homework_files')
            os.makedirs(save_dir, exist_ok=True)

            for file in files:
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    base, ext = os.path.splitext(filename)
                    timestamp = int(datetime.utcnow().timestamp())
                    unique_filename = f"{base}_{timestamp}{ext}"
                    save_path = os.path.join(save_dir, unique_filename)
                    file.save(save_path)
                    saved_file_paths.append(f'homework_files/{unique_filename}')

            files_json = json.dumps(saved_file_paths) if saved_file_paths else None

            new_homework = Homework(
                subject=subject,
                description=description,
                due_date=due_date,
                created_at=created_at,
                class_id=class_id,
                files=files_json,
                teacher_id=current_user.id
            )
            db.session.add(new_homework)
            db.session.commit()

            students = User.query.filter_by(class_id=class_id, role='student').all()
            for student in students:
                new_notification = Notification(
                    message=(
                        f"Новое домашнее задание по предмету {subject}: "
                        f"{description[:200]} "
                        f"Срок сдачи — {due_date.strftime('%d.%m.%Y')}"
                    ),
                    user_id=student.id,
                    notification_type='homework_added'
                )
                db.session.add(new_notification)
            db.session.commit()

            flash('✅ Домашнее задание добавлено!', 'success')

        return redirect(url_for('homework', date=selected_date))

    if current_user.role == 'student':
        start_of_day = selected_date_obj
        end_of_day = selected_date_obj + timedelta(days=1)

        homeworks = Homework.query.filter(
            Homework.class_id == current_user.class_id,
            Homework.created_at >= start_of_day,
            Homework.created_at < end_of_day
        ).all()

    elif current_user.role == 'teacher':
        homeworks = Homework.query.filter(
            Homework.created_at >= selected_date_obj,
            Homework.created_at < selected_date_obj + timedelta(days=1),
            Homework.teacher_id == current_user.id 
        ).all()


    else:
        homeworks = []

    return render_template(
        'homework.html',
        homeworks=homeworks,
        classes=classes,
        is_teacher=(current_user.role == 'teacher'),
        selected_date=selected_date,
        current_datetime=current_datetime,
        datetime=datetime
    )

from flask import request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not check_password_hash(current_user.password, current_password):
        flash('❌ Неверный текущий пароль', 'danger')
        return redirect(url_for('profile'))

    if new_password != confirm_password:
        flash('❌ Пароли не совпадают', 'danger')
        return redirect(url_for('profile'))

    if len(new_password) < 6:
        flash('❌ Новый пароль должен быть не менее 6 символов', 'danger')
        return redirect(url_for('profile'))

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    flash('✅ Пароль успешно обновлён!', 'success')
    return redirect(url_for('profile'))

@app.route('/profile')
@login_required
def profile():
    user = current_user

    from sqlalchemy import func, cast, Integer
    all_classes = SchoolClass.query.order_by(
        cast(func.substr(SchoolClass.name, 1, func.length(SchoolClass.name) - 1), Integer),
        func.substr(SchoolClass.name, -1, 1)
    ).all()

    teacher_class_ids = []
    if user.role == 'teacher':
        teacher_class_ids = [c.id for c in user.teacher_classes.all()]

    return render_template('profile.html', user=user, all_classes=all_classes, teacher_class_ids=teacher_class_ids)

@app.template_filter('calculate_age')
def calculate_age(birth_date):
    from datetime import date
    today = date.today()
    years = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    if 11 <= years % 100 <= 14:
        suffix = "лет"
    elif years % 10 == 1:
        suffix = "год"
    elif 2 <= years % 10 <= 4:
        suffix = "года"
    else:
        suffix = "лет"

    return f"{years} {suffix}"

@app.route('/update_teacher_classes', methods=['POST'])
@login_required
def update_teacher_classes():
    if current_user.role != 'teacher':
        flash('Только учителя могут редактировать классы.', 'danger')
        return redirect(url_for('profile'))

    selected_classes_ids = request.form.getlist('classes') 

    selected_classes_ids = list(map(int, selected_classes_ids))  

    selected_classes = SchoolClass.query.filter(SchoolClass.id.in_(selected_classes_ids)).all()

    current_user.teacher_classes = selected_classes
    db.session.commit()

    flash('Классы успешно обновлены.', 'success')
    return redirect(url_for('profile'))

from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user

UPLOAD_FOLDER = 'static/profile_pics' 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        last_name = request.form.get('last_name')
        age = request.form.get('age')

        current_user.first_name = request.form['first_name']
        current_user.last_name = request.form['last_name']
        birth_date_str = request.form.get('birth_date')
        if birth_date_str:
            current_user.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()


        avatar = request.files.get('avatar')
        if avatar and avatar.filename != '':
            if current_user.profile_picture:
                old_path = os.path.join(app.root_path, 'static/profile_pics', current_user.profile_picture)
                if os.path.exists(old_path):
                    os.remove(old_path)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
            filename = secure_filename(f"{timestamp}_{avatar.filename}")
            filepath = os.path.join(app.root_path, 'static/profile_pics', filename)

            avatar.save(filepath)

            current_user.profile_picture = filename

        db.session.commit()
        flash('Профиль успешно обновлён!', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html')

@app.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    if 'profile_picture' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['profile_picture']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file:
        filename = datetime.now().strftime("%Y-%m-%d_%H.%M.%S") + os.path.splitext(file.filename)[1]
        filepath = os.path.join('static/profile_pics', filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        file.save(filepath)

        current_user.profile_picture = filename
        db.session.commit()

        flash('Profile picture updated!')
        return redirect(url_for('profile'))
    
@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')  

@app.route('/grades_report', methods=['GET', 'POST'])
@login_required
def grades_report():
    if current_user.role != 'student':
        flash('Отчёт доступен только для учеников.')
        return redirect(url_for('index'))

    subjects = [
        'Математика', 'Русский язык', 'Физика', 
        'Химия', 'Биология', 'История', 'География'
    ]

    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        subject_averages = {}
        for subject in subjects:
            grades = Grade.query.filter_by(student_id=current_user.id, subject=subject) \
                .filter(Grade.date >= start_date, Grade.date <= end_date).all()
            if grades:
                avg = round(sum(g.grade for g in grades) / len(grades), 2)
            else:
                avg = 0
            subject_averages[subject] = avg

        period_text = f"График за период от {start_date.strftime('%d-%m-%Y')} до {end_date.strftime('%d-%m-%Y')}"
    else:
        subject_averages = {}
        for subject in subjects:
            grades = Grade.query.filter_by(student_id=current_user.id, subject=subject).all()
            if grades:
                avg = round(sum(g.grade for g in grades) / len(grades), 2)
            else:
                avg = 0
            subject_averages[subject] = avg

        period_text = "График оценок за все время"

    return render_template('grades_report.html', subject_averages=subject_averages, period_text=period_text)

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).limit(10).all()
        unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return dict(notifications=notifications, unread_count=unread_count)
    return dict(notifications=[], unread_count=0)

@app.route('/mark_notifications_read', methods=['POST'])
@login_required
def mark_notifications_read():
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    for note in notifications:
        note.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/clear_notifications', methods=['POST'])
@login_required
def clear_notifications():
    Notification.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Уведомления очищены.', 'success')
    return redirect(url_for('dashboard'))

from flask import jsonify, request, render_template
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

@app.route('/bind_child', methods=['POST'])
@login_required
def bind_child():
    if current_user.role != 'parent':
        flash('Только родители могут привязывать детей', 'danger')
        return redirect(url_for('dashboard'))  
    
    username = request.form.get('username') 
    password = request.form.get('password') 

    if not username:
        flash('Имя пользователя обязательно', 'danger')
        return redirect(url_for('dashboard')) 

    student = User.query.filter_by(username=username, role='student').first()
    if not student:
        flash('Ученик с таким именем не найден', 'danger')
        return redirect(url_for('dashboard')) 

    if student in current_user.children:
        flash('Этот ученик уже привязан к вам', 'danger')
        return redirect(url_for('dashboard')) 

    current_user.children.append(student)
    db.session.commit()

    flash('Ребёнок успешно привязан', 'success')
    return redirect(url_for('dashboard'))  

from flask import session

from flask import session, flash, redirect, url_for
from flask_login import login_user, current_user


@app.route('/switch_to_student/<int:student_id>')
def switch_to_student(student_id):
    student = User.query.get_or_404(student_id)

    if current_user.role != 'parent':
        flash('Вы не можете перейти к аккаунту ученика!', 'danger')
        return redirect(url_for('dashboard'))

    if student not in current_user.children:
        flash('Вы не можете перейти к аккаунту этого ученика!', 'danger')
        return redirect(url_for('dashboard'))

    session['parent_id'] = current_user.id  
    session['current_student'] = student.id  
    login_user(student)

    name_display = f"{student.first_name} {student.last_name}".strip() if student.first_name and student.last_name else student.username
    flash(f"Теперь вы вошли как {name_display}!", "success")

    return redirect(url_for('dashboard'))

@app.route('/switch_back_to_parent')
@login_required
def switch_back_to_parent():
    parent_id = session.get('parent_id')
    current_student_id = session.get('current_student')

    if current_user.role != 'student' or current_user.id != current_student_id or not parent_id:
        flash('Возврат невозможен: нет активной родительской сессии.', 'danger')
        return redirect(url_for('dashboard'))

    parent = User.query.get_or_404(parent_id)

    session.pop('parent_id', None)
    session.pop('current_student', None)

    login_user(parent)
    name_display = f"{parent.first_name} {parent.last_name}".strip() if parent.first_name and parent.last_name else parent.username
    flash(f"Вы вернулись в аккаунт родителя {name_display}.", "success")

    return redirect(url_for('dashboard'))

@app.route('/delete_user', methods=['POST'])
@login_required
def delete_user():
    if current_user.role != 'admin':
        flash('Только администратор может удалять пользователей.', 'danger')
        return redirect(url_for('dashboard'))

    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()

    if not user:
        flash('Пользователь не найден.', 'danger')
        return redirect(url_for('dashboard'))

    if not user.check_password(password):
        flash('Неверный пароль.', 'danger')
        return redirect(url_for('dashboard'))

    if user.id == current_user.id:
        flash('Нельзя удалить самого себя.', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь {username} удалён.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/manage_password_requests', methods=['GET', 'POST'])
@login_required
def manage_password_requests():
    if current_user.role != 'admin':
        flash('Доступ разрешён только администраторам!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        request_id = request.form.get('request_id')
        action = request.form.get('action')
        reset_request = PasswordResetRequest.query.get_or_404(request_id)

        if action == 'approve':
            user = reset_request.user
            password_option = request.form.get('password_option')
            if password_option == 'random':
                new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                user.password = generate_password_hash(new_password)
                reset_request.new_password = new_password
            elif password_option == 'custom':
                custom_password = request.form.get('custom_password')
                if len(custom_password) < 6:
                    flash('Пароль должен быть не менее 6 символов!', 'danger')
                    return redirect(url_for('manage_password_requests'))
                user.password = generate_password_hash(custom_password)
                reset_request.new_password = custom_password
            else:
                flash('Неверный выбор метода пароля!', 'danger')
                return redirect(url_for('manage_password_requests'))

            reset_request.status = 'approved'
            db.session.commit()
            db.session.add(Notification(
                message=f"Ваш запрос на сброс пароля одобрен. Новый пароль: {reset_request.new_password}",
                user_id=user.id,
                notification_type='password_reset_approved'
            ))
            db.session.commit()
            flash(f'Заявка для {user.username} одобрена. Новый пароль: {reset_request.new_password}', 'success')

        elif action == 'reject':
            reset_request.status = 'rejected'
            db.session.commit()
            db.session.add(Notification(
                message="Ваш запрос на сброс пароля отклонён.",
                user_id=reset_request.user_id,
                notification_type='password_reset_rejected'
            ))
            db.session.commit()
            flash(f'Заявка для {reset_request.user.username} отклонена.', 'info')

        return redirect(url_for('manage_password_requests'))

    requests = PasswordResetRequest.query.order_by(PasswordResetRequest.created_at.desc()).all()
    return render_template('manage_password_requests.html', requests=requests)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if SchoolClass.query.count() == 0:
            class_names = [f"{i}{letter}" for i in range(1, 12) for letter in "АБВ"]
            for name in class_names:
                db.session.add(SchoolClass(name=name))
            db.session.commit()
    app.run(debug=True)
