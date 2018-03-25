(function(){
var months = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
var wdays = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];

function dates (list) {
    return _.map(list, function (obj) {
        var m = obj[0].match(/^(\d\d\d\d)-(\d\d)-(\d\d)/);
        return parseInt(m[3], 10) + " " + months[parseInt(m[2], 10)-1];
        //var d = new Date(obj[0]);
        //return d.getDate() + " " + months[d.getMonth()];
    });
}

$(function () {
    $.getJSON("/stat/posters_weekly.json").success(function (users) {
        $("#stat-posters-weekly").highcharts({
            chart: {type: "bar"},
            title: {text: "Топ 20 постеров", x: -20},
            xAxis: {
            categories: _.map(users, function (obj) { return obj[0]; }),
                labels: {
                    align: 'right'
                }
            },
            yAxis: {
                title: {text: ""},
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }],
                min: 0
            },
            legend: {
                borderWidth: 0
            },
            series: [{
                name: "Посты",
                color: "#2f7ed8",
                data: _.map(users, function (obj) { return obj[1]; })
            }]
        });
    });

    $.getJSON("/stat/commenters_weekly.json").success(function (users) {
        $("#stat-commenters-weekly").highcharts({
            chart: {type: "bar"},
            title: {text: "Топ 20 комментаторов", x: -20},
            xAxis: {
            categories: _.map(users, function (obj) { return obj[0]; }),
                labels: {
                    align: 'right'
                }
            },
            yAxis: {
                title: {text: ""},
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }],
                min: 0
            },
            legend: {
                borderWidth: 0
            },
            series: [{
                name: "Комментарии",
                color: "#3cde8d",
                data: _.map(users, function (obj) { return obj[1]; })
            }]
        });
    });

    $.getJSON("/stat/most_commented_weekly.json").success(function (users) {
        $("#stat-most-commented-weekly").highcharts({
            chart: {type: "bar"},
            title: {text: "Топ 20 обсуждаемых пользователей", x: -20},
            xAxis: {
            categories: _.map(users, function (obj) { return obj[0]; }),
                labels: {
                    align: 'right'
                }
            },
            yAxis: {
                title: {text: ""},
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }],
                min: 0
            },
            legend: {
                borderWidth: 0
            },
            series: [{
                name: "Комментарии",
                color: "#3cde8d",
                data: _.map(users, function (obj) { return obj[1]; })
            }]
        });
    });

    $.when(
        $.getJSON("/stat/posts_avg.json"),
        $.getJSON("/stat/comments_avg.json")
    ).done(function (posts, comments) {
        $("#stat-avg").highcharts({
            chart: {type: "column"},
            title: {text: "Посты и комментарии по дням недели", x: -20},
            xAxis: {
                categories: wdays,
            },
            yAxis: {
                title: {text: ""},
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }],
                min: 0
            },
            legend: {
                borderWidth: 0
            },
            series: [
                {
                    name: "Посты",
                    data: posts[0],
                    color: "#2f7ed8"
                },
                {
                    name: "Комментарии",
                    data: comments[0],
                    color: "#3cde8d"
                }
            ]
        });
    });

    $.getJSON("/stat/users.json").success(function (users) {
        $("#stat-users").highcharts({
            title: {text: "Зарегистрировавшиеся пользователи", x: -20},
            xAxis: {
                categories: dates(users),
                labels: {
                    rotation: -90,
                    align: 'right',
                }
            },
            yAxis: {
                title: {text: ""},
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }],
                min: 0
            },
            legend: {
                borderWidth: 0
            },
            series: [{
                name: "Пользователи",
                data: _.map(users, function (obj) { return obj[1]; })
            }]
        });
    });

    $.when(
        $.getJSON("/stat/posts.json"),
        $.getJSON("/stat/comments.json")
    ).done(function (posts, comments) {
        $("#stat-posts").highcharts({
            title: {text: "Посты и комментарии", x: -20},
            xAxis: {
                categories: dates(posts[0]),
                labels: {
                    rotation: -90,
                    align: 'right',
                }
            },
            yAxis: {
                title: {text: ""},
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }],
                min: 0
            },
            legend: {
                borderWidth: 0
            },
            series: [
                {
                    name: "Посты",
                    data: _.map(posts[0], function (obj) { return obj[1]; }),
                    color: "#2f7ed8"
                },
                {
                    name: "Комментарии",
                    data: _.map(comments[0], function (obj) { return obj[1]; }),
                    color: "#3cde8d"
                }
            ]
        });
    });

    $.getJSON("/stat/blacklisted.json").success(function (users) {
        $("#stat-blacklisted").highcharts({
            chart: {type: "bar"},
            title: {text: "Топ 20 ненавидимых", x: -20},
            xAxis: {
            categories: _.map(users, function (obj) { return obj[0]; }),
                labels: {
                    align: 'right'
                }
            },
            yAxis: {
                title: {text: ""},
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }],
                min: 0
            },
            legend: {
                borderWidth: 0
            },
            series: [{
                name: "Пользователи",
                data: _.map(users, function (obj) { return obj[1]; })
            }]
        });
    });

    $.getJSON("/stat/blacklisters.json").success(function (users) {
        $("#stat-blacklisters").highcharts({
            chart: {type: "bar"},
            title: {text: "Топ 20 обидчивых и ранимых", x: -20},
            xAxis: {
            categories: _.map(users, function (obj) { return obj[0]; }),
                labels: {
                    align: 'right'
                }
            },
            yAxis: {
                title: {text: ""},
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: '#808080'
                }],
                min: 0
            },
            legend: {
                borderWidth: 0
            },
            series: [{
                name: "Пользователи",
                data: _.map(users, function (obj) { return obj[1]; })
            }]
        });
    });
});
})();

