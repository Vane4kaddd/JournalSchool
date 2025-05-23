import random
import string
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
from flask_migrate import Migrate
from sqlalchemy.orm import relationship
from sqlalchemy import func

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "instance", "school.db")}'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'  # Папка для хранения аватаров
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # Разрешенные расширения файлов
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

    # Ученики
    class_students = db.relationship(
        'User',
        back_populates='school_class',
        foreign_keys='User.class_id',
        overlaps="class_mentors, mentor_class"  
    )

    # Классные руководители
    class_mentors = db.relationship(
        'User',
        back_populates='mentor_class',
        foreign_keys='User.class_id',
        overlaps="class_students"
    )

parent_student = db.Table('parent_student',
    db.Column('parent_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

# Модель пользователя
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    role = db.Column(db.String(50), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=True)
    subject = db.Column(db.String(50)) 
    avatar = db.Column(db.String(200))
    school_class = db.relationship('SchoolClass', backref='students')
    phone = db.Column(db.String(20), nullable=True)

    
    def check_password(self, password):
        return check_password_hash(self.password, password)

    # Связь с детьми через таблицу parent_student
    children = db.relationship(
            'User',
            secondary=parent_student,
            primaryjoin=id==parent_student.c.parent_id,
            secondaryjoin=id==parent_student.c.student_id,
            backref='parents'
    )
    # Связь с классом
    school_class = db.relationship(
        'SchoolClass',
        back_populates='class_students',
        foreign_keys=[class_id]
    )
    # Связь с наставниками
    mentor_class = db.relationship(
        'SchoolClass',
        back_populates='class_mentors',
        foreign_keys=[class_id]
    )
    profile_picture = db.Column(db.String(100), nullable=True)


# Модель расписания
class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=False) 
    day = db.Column(db.String(20), nullable=False)
    time = db.Column(db.Time, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) 
    school_class = db.relationship('SchoolClass', backref=db.backref('schedules', lazy=True))
    teacher = db.relationship('User', backref='schedules')  


# Модель оценок
class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=False)  
    subject = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    school_class = db.relationship('SchoolClass', backref=db.backref('grades', lazy=True))  
    student = db.relationship('User', backref='grades', foreign_keys=[student_id])

# Модель домашнего задания
class Homework(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    class_id = db.Column(db.Integer, db.ForeignKey('school_class.id'), nullable=False)  
    school_class = db.relationship('SchoolClass', backref=db.backref('homeworks', lazy=True)) 
    
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form['username']
        phone = request.form['phone']
        
        # Проверяем пользователя по имени и телефону
        user = User.query.filter_by(username=username, phone=phone).first()
        
        if user:
            # Генерация нового пароля
            new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
            db.session.commit()
            
            # Отправка пароля на страницу
            flash(f'Ваш новый пароль: {new_password}', 'success')
            return redirect(url_for('reset_password'))
        else:
            # Если пользователь не найден
            flash('Неверные данные! Попробуйте снова.', 'danger')
    
    return render_template('reset_password.html')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/danger', methods=['GET', 'POST'])
def danger():
    if request.method == 'POST':
        password = request.form.get('school_password')
        if password == SCHOOL_PASSWORD:
            session['school_authenticated'] = True
            return redirect(url_for('home'))  # или 'dashboard'
        else:
            flash('Неверный пароль школы', 'danger')
    return render_template('danger.html')

@app.before_request
def require_school_password():
    # разрешён доступ только к '/' и статике до ввода пароля
    allowed_routes = ['danger', 'static']
    if not session.get('school_authenticated') and request.endpoint not in allowed_routes:
        return redirect(url_for('danger'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Список классов для ученика
    classes = SchoolClass.query.all()
    # Список предметов для учителей
    subjects = ["Математика", "Русский язык", "Физика", "Химия", "Биология", "История", "География"]

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        class_id = request.form.get('class_id')  # Получаем значение из формы для ученика
        subject = request.form.get('subject')  # Получаем значение из формы для учителя
        phone = request.form.get('phone')

        # Преобразуем class_id в целое число (если оно указано)
        if class_id:
            class_id = int(class_id)

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Проверка на существование пользователя с таким же username
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует!', 'danger')
            return redirect(url_for('register'))

        # Создаем нового пользователя
        new_user = User(username=username, password=hashed_password, role=role)
        new_user.phone = phone  # <-- перемещено сюда, после создания объекта

        # Если роль "ученик", связываем класс с пользователем
        if role == 'student':
            if not class_id:
                flash('Для ученика нужно выбрать класс!', 'danger')
                return redirect(url_for('register'))

            school_class = SchoolClass.query.get(class_id)
            if not school_class:
                flash('Выбранный класс не существует!', 'danger')
                return redirect(url_for('register'))

            new_user.class_id = school_class.id

        # Если роль "учитель", связываем предмет с пользователем
        elif role == 'teacher':
            if not subject:
                flash('Для учителя нужно выбрать предмет!', 'danger')
                return redirect(url_for('register'))
            
            new_user.subject = subject

        # Для админа ничего не добавляем

        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация успешна! Теперь войдите.', 'success')
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
            flash('Вход выполнен!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль!', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    print(f"Текущая роль: {current_user.role}")

    # Для родителя - отображаем привязанных детей
    children = []
    if current_user.role == 'parent':  # Если роль родителя
        children = current_user.children  # Получаем привязанных детей

    return render_template('dashboard.html', username=current_user.username, 
                           role=current_user.role, children=children)

# 🔹 Расписание
@app.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    classes = SchoolClass.query.all()
    teachers = User.query.filter_by(role='teacher').order_by(User.last_name).all()
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]

    # Получение выбранного дня
    selected_day = request.args.get('day', days[0])  # По умолчанию Понедельник

    # Получение/сохранение выбранного класса
    selected_class_id = request.args.get('selected_class')
    if current_user.role == 'admin':
        if selected_class_id:
            session['selected_class_id'] = selected_class_id
        else:
            selected_class_id = session.get('selected_class_id')

        if not selected_class_id:
            return redirect(url_for('class_select'))

    # Если класс не выбран и роль администратора, перенаправляем на выбор класса
    if current_user.role == 'admin' and not selected_class_id:
        return redirect(url_for('class_select'))

    # Получение расписания в зависимости от роли
    if current_user.role == 'student':
        lessons = Schedule.query.filter_by(day=selected_day, class_id=current_user.class_id).order_by(Schedule.time).all()
    elif current_user.role == 'teacher':
        lessons = Schedule.query.filter_by(day=selected_day, teacher_id=current_user.id).order_by(Schedule.time).all()
    elif current_user.role == 'admin':
        lessons = Schedule.query.filter_by(day=selected_day, class_id=selected_class_id).order_by(Schedule.time).all()
    else:
        lessons = []

    # Обработка POST-запросов только для администратора
    if request.method == 'POST' and current_user.role == 'admin':
        action = request.form.get('action')

        if action == 'add':
            day = request.form.get('day')
            time_str = request.form.get('time')
            subject = request.form.get('subject')
            class_id = request.form.get('class_id')
            teacher_id = request.form.get('teacher')

            if not day or not time_str or not subject or not class_id or not teacher_id:
                flash('Все поля должны быть заполнены!', 'danger')
                return redirect(url_for('schedule', day=selected_day, selected_class=selected_class_id))

            try:
                time_obj = datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                flash('Некорректный формат времени!', 'danger')
                return redirect(url_for('schedule', day=selected_day, selected_class=selected_class_id))

            new_schedule = Schedule(
                day=day, time=time_obj, subject=subject, teacher_id=teacher_id, class_id=class_id
            )
            db.session.add(new_schedule)
            db.session.commit()
            # 🔔 Уведомления о добавлении расписания
            students = User.query.filter_by(class_id=class_id, role='student').all()
            for student in students:
                new_notification = Notification(
                    message=f"Добавлено новое занятие: {subject} ({day}, {time_str})",
                    user_id=student.id,
                    notification_type='schedule_updated'
                )
                db.session.add(new_notification)
            db.session.commit()
            flash('Расписание добавлено!', 'success')

        elif action == 'delete':
            schedule_id = request.form.get('schedule_id')
            lesson = Schedule.query.get(schedule_id)

            if lesson:
                # 🔔 Уведомления об удалении занятия
                students = User.query.filter_by(class_id=lesson.class_id, role='student').all()
                for student in students:
                    new_notification = Notification(
                        message=f"Удалено занятие: {lesson.subject} ({lesson.day}, {lesson.time.strftime('%H:%M')})",
                        user_id=student.id,
                        notification_type='schedule_updated'
                    )
                    db.session.add(new_notification)

                db.session.delete(lesson)
                db.session.commit()
                flash('Запись удалена!', 'success')
            else:
                flash('Запись не найдена!', 'danger')

        return redirect(url_for('schedule', day=selected_day, selected_class=selected_class_id))

    return render_template(
        'schedule.html',
        lessons=lessons,
        classes=classes,
        teachers=teachers,
        days=days,
        selected_day=selected_day,
        selected_class_id=selected_class_id  # Передаем selected_class_id
    )


# Модель оценок
@app.route('/grades', methods=['GET', 'POST'])
@login_required
def grades():
    classes = SchoolClass.query.all()

    # Получаем выбранную дату (по умолчанию сегодня)
    selected_date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

    if current_user.role == 'student':
        # Показываем оценки ученика за выбранную дату
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
            # Проверка существования класса
            school_class = SchoolClass.query.get(selected_class_id)
            if not school_class:
                flash("Класс не найден.", "danger")
                return redirect(url_for('grades', date=selected_date))

            students = User.query.filter_by(role='student', class_id=selected_class_id).order_by(User.last_name).all()

        if request.method == 'POST':
            try:
                user_id = int(request.form.get('user_id'))  # Получаем ID ученика
                subject = request.form.get('subject')
                grade_value = int(request.form.get('grade'))
                date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()

                student = User.query.get(user_id)

                if not student or student.role != "student":
                    flash("Ученик не найден!", "danger")
                    return redirect(url_for('grades', class_id=selected_class_id, date=selected_date))

                if not student.class_id:
                    flash("У ученика не указан class_id, оценка не может быть сохранена.", "danger")
                    return redirect(url_for('grades', class_id=selected_class_id, date=selected_date))

                if grade_value < 1 or grade_value > 5:  # Допустимый диапазон оценок
                    flash("Оценка должна быть в пределах от 1 до 5.", "danger")
                    return redirect(url_for('grades', class_id=selected_class_id, date=selected_date))

                # Создаем и сохраняем новую оценку
                new_grade = Grade(
                    student_id=student.id,
                    class_id=student.class_id,
                    subject=subject,
                    grade=grade_value,
                    date=date
                )
                db.session.add(new_grade)
                db.session.commit()

                # 🔔 Добавляем уведомление ученику
                new_notification = Notification(
                    message=f"Вам поставлена оценка {grade_value} по предмету {subject} за {date.strftime('%d.%m.%Y')}",
                    user_id=student.id,
                    notification_type='grade_added'
                )
                db.session.add(new_notification)
                db.session.commit()

                flash("Оценка добавлена!", "success")

            except ValueError:
                flash("Ошибка: неверный формат данных.", "danger")
            except Exception as e:
                flash(f"Произошла ошибка: {str(e)}", "danger")

        # Показываем все оценки за дату
        all_grades = Grade.query.filter_by(date=selected_date_obj).all()

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
        return redirect(url_for('home'))  # или другую страницу, если нет прав



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
        db.session.delete(grade)
        db.session.commit()
        flash("Оценка удалена!", "success")

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
    classes = SchoolClass.query.all()
    current_datetime = datetime.utcnow()

    # Получаем выбранную дату (по умолчанию - сегодня)
    selected_date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()

    # Логика удаления домашнего задания
    if request.method == 'POST' and 'action' in request.form:
        action = request.form['action']
        if action == 'delete' and current_user.role == 'teacher':
            homework_id = request.form['homework_id']
            homework_to_delete = Homework.query.get(homework_id)
            if homework_to_delete:
                db.session.delete(homework_to_delete)
                db.session.commit()
                flash('Домашнее задание удалено!', 'success')
            else:
                flash('Ошибка: домашнее задание не найдено.', 'danger')

        elif action == 'add' and current_user.role == 'teacher':
            subject = request.form['subject']
            description = request.form['description']

            # Дата сдачи не требуется для добавления задания, но она может быть указана для учителя
            if 'due_date' in request.form:
                try:
                    due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date()
                except ValueError:
                    flash('Неверный формат даты сдачи', 'danger')
                    return redirect(url_for('homework'))
            else:
                flash('Дата сдачи не указана', 'danger')
                return redirect(url_for('homework'))

            # Дата создания - текущее время
            created_at = datetime.utcnow()

            # Получаем ID класса
            class_id = request.form['class_id']

            # Создание нового домашнего задания
            new_homework = Homework(subject=subject, description=description, due_date=due_date, created_at=created_at, class_id=class_id)
            db.session.add(new_homework)
            db.session.commit()

            # Уведомления для всех учеников этого класса
            students = User.query.filter_by(class_id=class_id, role='student').all()
            if students:
                for student in students:
                    new_notification = Notification(
                        message=(
                            f"Новое домашнее задание по предмету {subject}: "
                            f"{description[:200]}"  # обрезаем описание до 100 символов
                            f" Срок сдачи — {due_date.strftime('%d.%m.%Y')}"
                        ),
                        user_id=student.id,
                        notification_type='homework_added'
                    )
                    db.session.add(new_notification)
                db.session.commit()
            else:
                flash('Нет студентов в этом классе', 'warning')

            flash('Домашнее задание добавлено!', 'success')

        return redirect(url_for('homework', date=selected_date))

    # Фильтрация домашних заданий по выбранной дате (на основе created_at)
    if current_user.role == 'student':
        # Для студентов: показываем задания, созданные в выбранный день
        start_of_day = selected_date_obj
        end_of_day = selected_date_obj + timedelta(days=1)  # конец дня

        homeworks = Homework.query.filter(
            Homework.class_id == current_user.class_id,
            Homework.created_at >= start_of_day,
            Homework.created_at < end_of_day
        ).all()

    elif current_user.role == 'teacher':
        # Для учителей: показываем все задания, созданные в выбранный день
        homeworks = Homework.query.filter(
            Homework.created_at >= selected_date_obj,
            Homework.created_at < selected_date_obj + timedelta(days=1)
        ).all()

    else:
        # Для администратора нет возможности видеть задания
        homeworks = []

    # Передаем переменную datetime в шаблон
    return render_template('homework.html', homeworks=homeworks, classes=classes, 
                           is_teacher=(current_user.role == 'teacher'), selected_date=selected_date,
                           current_datetime=current_datetime, datetime=datetime)  # Добавляем datetime



from flask import request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Проверка текущего пароля
    if not check_password_hash(current_user.password, current_password):
        flash('❌ Неверный текущий пароль', 'danger')
        return redirect(url_for('profile'))

    # Проверка совпадения нового пароля
    if new_password != confirm_password:
        flash('❌ Пароли не совпадают', 'danger')
        return redirect(url_for('profile'))

    # Проверка длины нового пароля
    if len(new_password) < 6:
        flash('❌ Новый пароль должен быть не менее 6 символов', 'danger')
        return redirect(url_for('profile'))

    # Обновление пароля
    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    flash('✅ Пароль успешно обновлён!', 'success')
    return redirect(url_for('profile'))

@app.route('/profile')
@login_required
def profile():
    user = current_user
    return render_template('profile.html', user=user)

from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user

UPLOAD_FOLDER = 'static/profile_pics'  # Папка для хранения аватаров
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        last_name = request.form.get('last_name')
        age = request.form.get('age')

        # Обновляем основные поля
        current_user.first_name = request.form['first_name']
        current_user.last_name = request.form['last_name']
        current_user.age = request.form['age']

        # Обработка аватара
        avatar = request.files.get('avatar')
        if avatar and avatar.filename != '':
            # Удалим старое изображение (опционально)
            if current_user.profile_picture:
                old_path = os.path.join(app.root_path, 'static/profile_pics', current_user.profile_picture)
                if os.path.exists(old_path):
                    os.remove(old_path)

            # Генерируем уникальное имя
            timestamp = datetime.now().strftime("%Y-%m-%d_%H.%M.%S")
            filename = secure_filename(f"{timestamp}_{avatar.filename}")
            filepath = os.path.join(app.root_path, 'static/profile_pics', filename)

            # Сохраняем файл
            avatar.save(filepath)

            # Сохраняем имя файла в базу
            current_user.profile_picture = filename

        # Сохраняем изменения
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
        
        # ✅ Создание папки, если не существует (на всякий случай)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        file.save(filepath)

        # Обновим профиль пользователя
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

    # Фиксированный список предметов
    subjects = [
        'Математика', 'Русский язык', 'Физика', 
        'Химия', 'Биология', 'История', 'География'
    ]

    # Извлекаем фильтры
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    # Обработка дат (если они выбраны)
    if start_date and end_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        # Считаем средние оценки по каждому предмету за выбранный период
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
        # Считаем средние оценки по каждому предмету за все время
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


@app.route('/schedule/class-select')
@login_required
def class_select():
    if current_user.role != 'admin':
        return redirect(url_for('schedule'))

    classes = SchoolClass.query.all()
    return render_template('class_select.html', classes=classes)

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        # Получаем уведомления для текущего пользователя, отсортированные по времени
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
        return redirect(url_for('dashboard'))  # Перенаправление на нужную страницу, например, dashboard
    
    username = request.form.get('username')  # Получаем имя пользователя из формы
    password = request.form.get('password')  # Получаем пароль из формы

    if not username:
        flash('Имя пользователя обязательно', 'danger')
        return redirect(url_for('dashboard'))  # Перенаправление с сообщением об ошибке

    # Проверка, существует ли ученик с таким именем
    student = User.query.filter_by(username=username, role='student').first()
    if not student:
        flash('Ученик с таким именем не найден', 'danger')
        return redirect(url_for('dashboard'))  # Перенаправление с сообщением об ошибке

    # Привязываем ученика к родителю
    if student in current_user.children:
        flash('Этот ученик уже привязан к вам', 'danger')
        return redirect(url_for('dashboard'))  # Перенаправление с сообщением об ошибке

    current_user.children.append(student)
    db.session.commit()

    flash('Ребёнок успешно привязан', 'success')
    return redirect(url_for('dashboard'))  # Перенаправление на страницу с детьми или в профиль



from flask import session

from flask import session, flash, redirect, url_for
from flask_login import login_user, current_user


@app.route('/switch_to_student/<int:student_id>')
def switch_to_student(student_id):
    student = User.query.get_or_404(student_id)

    # Проверяем, что текущий пользователь - родитель
    if current_user.role != 'parent':
        flash('Вы не можете перейти к аккаунту ученика!', 'danger')
        return redirect(url_for('dashboard'))

    # Проверяем, что родитель привязал этого ученика
    if student not in current_user.children:
        flash('Вы не можете перейти к аккаунту этого ученика!', 'danger')
        return redirect(url_for('dashboard'))

    # Сохраняем информацию о родителе в сессии
    session['parent_id'] = current_user.id  # Сохраняем ID родителя для возврата
    session['current_student'] = student.id  # Сохраняем ID ученика для отображения кнопки возврата

    # Логиним родителя как ученика
    login_user(student)

    flash(f'Теперь вы вошли как {student.username}!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/switch_back_to_parent')
@login_required
def switch_back_to_parent():
    # Проверка: пользователь действительно ученик и был переключён родителем
    parent_id = session.get('parent_id')
    current_student_id = session.get('current_student')

    if current_user.role != 'student' or current_user.id != current_student_id or not parent_id:
        flash('Возврат невозможен: нет активной родительской сессии.', 'danger')
        return redirect(url_for('dashboard'))

    parent = User.query.get_or_404(parent_id)

    # Очищаем временные переменные из сессии
    session.pop('parent_id', None)
    session.pop('current_student', None)

    login_user(parent)
    flash(f'Вы вернулись в аккаунт родителя {parent.username}.', 'success')
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

    # Проверка пароля
    if not user.check_password(password):
        flash('Неверный пароль.', 'danger')
        return redirect(url_for('dashboard'))

    # Защита от удаления себя
    if user.id == current_user.id:
        flash('Нельзя удалить самого себя.', 'danger')
        return redirect(url_for('dashboard'))

    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь {username} удалён.', 'success')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if SchoolClass.query.count() == 0:
            class_names = [f"{i}{letter}" for i in range(1, 12) for letter in "АБВ"]
            for name in class_names:
                db.session.add(SchoolClass(name=name))
            db.session.commit()
    app.run(debug=True)