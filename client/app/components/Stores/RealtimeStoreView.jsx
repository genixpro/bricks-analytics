import React from 'react';
import axios from 'axios';
import {withRouter} from "react-router-dom";
import { Grid, Row, Col, Panel, Button, FormControl, FormGroup, InputGroup, DropdownButton, MenuItem, Tab, Tabs, Nav, NavItem } from 'react-bootstrap';
import ZoneEditor from './ZoneEditor';
import _ from 'underscore';
import Transition from 'react-transition-group/Transition';


class RealtimeStoreView extends React.Component {
    constructor(props) {
        super(props);

        this.state = {};
    }

    componentDidMount()
    {
        var headers = {durable: false, "auto-delete": true, exclusive: true};
        this.storeSubscription = this.props.messagingClient.subscribe("/exchange/store-time-series-frames-" + this.props.store._id, (message) =>
        {
            const body = JSON.parse(message.body);

            const newState = {
                frame: body,
                fadingPeople: []
            };

            if (this.state.frame)
            {
                this.state.frame.people.forEach((person) =>
                {
                    let found = false;
                    newState.frame.people.forEach((person2) =>
                    {
                        if (person.visitorId === person2.visitorId)
                        {
                            found = true;
                        }
                    });

                    if (!found)
                    {
                        const fadingPerson = _.clone(person);
                        newState.fadingPeople.push(fadingPerson);
                    }
                });
            }

            this.setState(newState);
        }, headers);
    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {
        if (this.storeSubscription)
        {
            this.storeSubscription.unsubscribe();
        }
    }


    render() {
        const transitionDuration = 750;

        const personEnterTransitionStyles = {
            entering: { opacity: 0 },
            entered:  { opacity: 1 }
        };

        const personExitTransitionStyles = {
            entering: { opacity: 1 },
            entered:  { opacity: 0 }
        };

        const drawPerson = (person, fading) => {
            return <Transition
                in={true}
                appear={true}
                key={person.visitorId}
                timeout={transitionDuration}>
                {(state) => (
                    <div
                        className={"person-location-box " + state}
                        style={_.extend({
                            "left": "calc(" + (person["x"] * 100) + "% - 30px)",
                            "top": "calc(" + (person["y"] * 100) + "% - 30px)",
                            "opacity": 0,
                            "transition": `left ${transitionDuration}ms ease-in-out, top ${transitionDuration}ms ease-in-out, opacity ${transitionDuration}ms ease-in-out`
                        }, fading ? personExitTransitionStyles[state] : personEnterTransitionStyles[state])}>
                        <div className={"person-image-wrapper"}>
                            <img className="person-image"
                                 src='/img/person.png'
                            />
                        </div>
                        <div className={"visitor-id-block"}>
                            <span>{person.visitorId}</span>
                        </div>
                    </div>
                )}
            </Transition>;
        };

        return (
            <div className={"realtime-store-view"}>
                <br/>
                <Panel>
                    <Row>
                        <Col xs={12}>
                            <h2>Realtime Store View</h2>
                            <div className="storeMap">
                                <img className='store-image' src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout"} />
                                {this.state.frame && this.state.frame.people.map((person) => drawPerson(person, false))}
                                {this.state.fadingPeople && this.state.fadingPeople.map((person) => drawPerson(person, true))}
                            </div>
                        </Col>
                    </Row>
                </Panel>
            </div>
        );
    }
}

export default withRouter(RealtimeStoreView);


