import React from 'react';
import {Miss, Redirect, Route, Switch, withRouter} from 'react-router-dom';
import {CSSTransition, TransitionGroup} from 'react-transition-group';

import Base from './components/Layout/Base';
import BasePage from './components/Layout/BasePage';

import Dashboard from './components/Dashboard/Dashboard';
import NewStore from './components/Stores/NewStore';
import FindStore from './components/Stores/FindStore';
import ViewStore from './components/Stores/ViewStore';
import StoreDetails from './components/Stores/StoreDetails';
import StoreImageProcessors from './components/Stores/StoreImageProcessors';
import StoreCameras from './components/Stores/StoreCameras';
import Login from './components/Authentication/Login';
import AuthCallback from './components/Authentication/AuthCallback';
import SubMenu from './components/SubMenu/SubMenu';
import MiniPOS from './components/MiniPOS/mini_pos';
import MiniPOSSecondaryScreen from './components/MiniPOS/mini_pos_secondary_screen';
import Auth from './services/Auth';
import _ from 'underscore';
import {Stomp} from "stompjs/lib/stomp.min";


// Create the global authentication service
const auth = new Auth();

// Create the global websocket service for realtime messaging
let ws = new WebSocket('ws://localhost:15674/ws');
let messagingClient =  Stomp.over(ws);

messagingClient.debug = function(str) {
    // debugging messaging
    // console.log("HERE!", str);
};

const onError = () => {
    // Just keep reconnecting after 1 second timeout
    setTimeout(() =>
    {
        messagingClient.connect("guest", "guest", () => {}, onError);
    }, 1000);
};

messagingClient.connect("guest", "guest", () => {}, onError);

// List of routes that uses the page layout
// listed here to Switch between layouts
// depending on the current pathname
const listofPages = [
    '/login/callback',
    '/login',
    '/minipos',
    '/minipos_secondary',
    /* See full project for reference */
];


class PrivateRoute extends React.Component {
    render() {
        const SubComponent = this.props['component'];
        const newProps = _.omit(this.props, 'component');

        const additionalProps = {
            auth: auth,
            messagingClient: messagingClient
        };

        const v = (<Route
            {...newProps}
            render={props =>
                auth.isAuthenticated() ? (
                    <SubComponent {...props} {...additionalProps}>{this.props.children}</SubComponent>
                ) : (
                    <Redirect
                        to={{
                            pathname: "/login",
                            state: {from: props.location}
                        }}
                    />
                )
            }
        />);
        return v;
    }
}

const Routes = ({location}) => {
    const currentKey = location.pathname.split('/')[1] || '/';
    const timeout = {enter: 500, exit: 500};

    // Animations supported
    //      'rag-fadeIn'
    //      'rag-fadeInUp'
    //      'rag-fadeInDown'
    //      'rag-fadeInRight'
    //      'rag-fadeInLeft'
    //      'rag-fadeInUpBig'
    //      'rag-fadeInDownBig'
    //      'rag-fadeInRightBig'
    //      'rag-fadeInLeftBig'
    //      'rag-zoomBackDown'
    const animationName = 'rag-fadeIn'

    if (listofPages.indexOf(location.pathname) > -1) {
        return (
            // Page Layout component wrapper
            <BasePage>
                <Switch location={location}>
                    <Route path="/login/callback" render={(props) => <AuthCallback auth={auth} {...props} />}/>
                    <Route path="/login" render={(props) => <Login auth={auth} {...props} />}/>
                    <Route path="/minipos" render={(props) => <MiniPOS  {...props} />} />
                    <Route path="/minipos_secondary" render={(props) => <MiniPOSSecondaryScreen  {...props} />} />
                    {/* See full project for reference */}
                </Switch>
            </BasePage>
        )
    }
    else {
        return (
            // Layout component wrapper
            // Use <BaseHorizontal> to change layout
            <Base>
                <TransitionGroup>
                    <CSSTransition key={currentKey} timeout={timeout} classNames={animationName}>
                        <div>
                            <Switch location={location}>
                                <PrivateRoute path="/singleview" component={Dashboard} />
                                <PrivateRoute path="/submenu" component={SubMenu} />
                                <PrivateRoute path="/new-store" component={NewStore} />
                                <PrivateRoute path="/find-store" component={FindStore} />
                                <PrivateRoute path="/store/:storeId" component={ViewStore} />
                                <Redirect to="/singleview"/>
                            </Switch>
                        </div>
                    </CSSTransition>
                </TransitionGroup>
            </Base>
        )
    }
}

export default withRouter(Routes);
